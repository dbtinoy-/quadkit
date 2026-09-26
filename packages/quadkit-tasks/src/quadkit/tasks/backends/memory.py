"""In-memory task queue implementation

This module provides a memory-based task queue using heap for priority ordering.
Suitable for development, testing, and single-process applications.
"""

from __future__ import annotations

import asyncio
import heapq
import time
from typing import TYPE_CHECKING

from quadkit.contracts.infra.tasks import TaskQueueProtocol
from quadkit.result import Ok, Result
from quadkit.tasks.constants import DEFAULT_QUEUE_NAME
from quadkit.tasks.exceptions import TaskError
from quadkit.tasks.hooks import TaskEnqueuedHook
from quadkit.tasks.models.job import JobProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core import HookRegistryProtocol


class MemoryTaskQueue(TaskQueueProtocol):
    """In-memory task queue implementation

    Uses Python's heapq for priority-based ordering. Tasks are stored
    in memory and will be lost on process restart. Thread-safe using
    asyncio.Lock for concurrent access.

    Characteristics:
    - Storage: In-memory heap-based priority queue
    - Concurrency: asyncio.Lock for thread safety
    - Persistence: No persistence (volatile)
    - Use Case: Development, testing, single-process applications
    - Limitations: No persistence, single-process only

    Example:
        ```python
        queue = MemoryTaskQueue()
        await queue.enqueue(task)
        task = await queue.dequeue()
        ```
    """

    def __init__(self) -> None:
        """Initialize memory task queue"""
        self.tasks: list[tuple[int, float, JobProtocol]] = []
        self._lock = asyncio.Lock()
        self._in_flight: dict[str, tuple[int, float, JobProtocol]] = {}
        self._hooks: HookRegistryProtocol | None = None

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry after provider boot wiring."""
        self._hooks = hooks

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a task action hook when a registry is available."""
        hooks = getattr(self, "_hooks", None)
        if hooks is None:
            return

        await hooks.call_action(hook_name, payload=payload)

    async def enqueue(self, task: JobProtocol) -> Result[str, TaskError]:  # type: ignore[override]
        """Add a task to the queue, returning Ok(task_id) or Err(TaskError) on failure.

        Tasks are stored in a min-heap with negative priority
        to achieve max-heap behavior (highest priority first).

        Args:
            task: Task to enqueue

        Returns:
            Ok containing the enqueued task id, or Err containing a TaskError.
        """
        async with self._lock:
            # Use negative priority for max-heap behavior.  created_at is
            # optional on JobProtocol; fall back to 0.0 for ordering.
            created_at = getattr(task, "created_at", None)
            if not isinstance(created_at, (int, float)):
                created_at = 0.0
            heapq.heappush(self.tasks, (-task.priority, created_at, task))
        await self._emit_action(
            "task.queued",
            TaskEnqueuedHook(task_name=task.name, queue_name=DEFAULT_QUEUE_NAME),
        )
        return Ok(task.id)

    async def dequeue(self) -> JobProtocol | None:
        """Remove and return the next task from the queue

        Returns the highest priority task. If multiple tasks have
        the same priority, returns the oldest (FIFO).
        Respects task delay - tasks with future available_at are skipped.

        Returns:
            Next task or None if queue is empty or no tasks are available
        """
        async with self._lock:
            now = time.time()
            # Find next available task (respecting delay)
            while self.tasks:
                priority, created_at, task = heapq.heappop(self.tasks)
                # Check if task's delay has passed.  scheduled_at /
                # created_at are optional on JobProtocol; only numeric
                # timestamps are usable, otherwise the job is due now.
                scheduled_at = getattr(task, "scheduled_at", None)
                # created_at is typed float by the heap tuple, so it always
                # provides a usable fallback timestamp.
                if isinstance(scheduled_at, (int, float)) and scheduled_at > 0:
                    available_at = scheduled_at
                else:
                    available_at = created_at
                if available_at <= now:
                    self._in_flight[task.id] = (priority, created_at, task)
                    return task
                # Put back - task not yet available
                heapq.heappush(self.tasks, (priority, created_at, task))
                break
            return None

    async def ack(self, task_id: str) -> None:
        """Acknowledge successful processing of a task

        Removes the task from the in-flight tracking set.

        Args:
            task_id: ID of the task to acknowledge
        """
        async with self._lock:
            self._in_flight.pop(task_id, None)

    async def nack(self, task_id: str, requeue: bool = True) -> None:
        """Negative-acknowledge a task, optionally requeuing it

        Removes the task from in-flight tracking. If requeue is True
        the task is pushed back onto the priority heap for retry.

        Args:
            task_id: ID of the task to negative-acknowledge
            requeue: If True, return the task to the queue for retry
        """
        async with self._lock:
            entry = self._in_flight.pop(task_id, None)
            if entry is not None and requeue:
                heapq.heappush(self.tasks, entry)

    async def get_task_count(self) -> int:
        """Get the number of tasks in the queue

        Returns:
            Number of pending tasks
        """
        async with self._lock:
            return len(self.tasks)

    async def clear(self) -> None:
        """Clear all tasks from the queue"""
        async with self._lock:
            self.tasks.clear()

    async def close(self) -> None:
        """Close the queue connection

        For memory queue, there are no external resources to clean up.
        """
        # Nothing to close for in-memory queue
