"""Mock implementations for task queue and executor testing.

Provides :class:`MockTaskQueue`, :class:`MockTaskExecutor`, and
:class:`MockTasksProvider` for use in unit tests that need to simulate task
enqueue/dequeue and handler dispatch without a real backend.
"""

from __future__ import annotations

import contextlib
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from quadkit.contracts.infra.tasks.exceptions import TaskQueueError

T = TypeVar("T")


@dataclass
class MockTaskResult(Generic[T]):
    """Lightweight result wrapper returned by :class:`MockTaskExecutor`.

    Provides ``.success``, ``.value``, and ``.error`` attributes for
    test assertions without importing the full tasks package.
    """

    success: bool
    value: T | None = field(default=None)
    error: str | None = field(default=None)


class MockTaskQueue:
    """In-memory task queue for testing.

    Supports enqueue, dequeue, cancellation, and basic statistics with no
    external dependencies.

    Example:
        ```python
        queue = MockTaskQueue()
        task_id = await queue.enqueue(task)
        task = await queue.dequeue()
        ```
    """

    def __init__(self) -> None:
        self._queue: list[Any] = []  # ordered items waiting to be processed
        self._store: dict[str, Any] = {}  # id -> task (pending only)
        self._in_flight: dict[str, Any] = {}  # id -> task (dequeued, awaiting ack/nack)
        self._completed: int = 0

    async def enqueue(self, task: Any) -> Result[str, TaskQueueError]:
        """Place *task* at the back of the queue and return Ok(task_id).

        Args:
            task: Any object with an ``id`` attribute.

        Returns:
            Ok containing the task's ``id``.
        """
        self._queue.append(task)
        self._store[task.id] = task
        return Ok(task.id)

    async def dequeue(self) -> Any | None:
        """Remove and return the front task, or ``None`` if the queue is empty.

        Increments the completed-task counter upon successful dequeue.

        Returns:
            The next task, or ``None``.
        """
        if not self._queue:
            return None
        task = self._queue.pop(0)
        self._store.pop(task.id, None)
        self._in_flight[task.id] = task
        self._completed += 1
        return task

    async def ack(self, task_id: str) -> None:
        """Acknowledge successful processing of a dequeued task.

        Removes the task from the in-flight tracking dict.

        Args:
            task_id: Identifier of the task to acknowledge.
        """
        self._in_flight.pop(task_id, None)

    async def nack(self, task_id: str, requeue: bool = True) -> None:
        """Negative-acknowledge a dequeued task, optionally requeuing it.

        If ``requeue`` is True the task is returned to the front of the
        queue for another processing attempt and the completed counter is
        decremented.  Either way the task is removed from the in-flight
        tracking dict.

        Args:
            task_id: Identifier of the task to negative-acknowledge.
            requeue: If True, return the task to the front of the queue.
        """
        task = self._in_flight.pop(task_id, None)
        if task is not None and requeue:
            self._queue.insert(0, task)
            self._store[task.id] = task
            self._completed = max(0, self._completed - 1)

    async def get_task_count(self) -> int:
        """Return the number of pending (not yet dequeued) tasks.

        Returns:
            Number of tasks waiting to be dequeued.
        """
        return len(self._queue)

    async def clear(self) -> None:
        """Remove all pending and in-flight tasks."""
        self._queue.clear()
        self._store.clear()
        self._in_flight.clear()

    async def close(self) -> None:
        """No-op – the mock has no external resources to close."""

    async def get_task(self, task_id: str) -> Any | None:
        """Return the pending task with *task_id*, or ``None`` if not found.

        Args:
            task_id: Identifier of the task to retrieve.

        Returns:
            The task if still pending, otherwise ``None``.
        """
        return self._store.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Remove a pending task from the queue.

        Args:
            task_id: Identifier of the task to cancel.

        Returns:
            ``True`` if the task was found and removed, ``False`` otherwise.
        """
        if task_id not in self._store:
            return False
        task = self._store.pop(task_id)
        with contextlib.suppress(ValueError):
            self._queue.remove(task)
        return True

    async def get_queue_stats(self) -> dict[str, int]:
        """Return basic queue statistics.

        Returns:
            A dict with ``queued`` (pending count) and ``completed`` keys.
        """
        return {"queued": len(self._queue), "completed": self._completed}

    async def clear_queue(self) -> None:
        """Remove all pending tasks from the queue."""
        self._queue.clear()
        self._store.clear()

    def get_all(self) -> list[Any]:
        """Return a snapshot of all pending tasks in queue order.

        Returns:
            List of all tasks currently in the queue.
        """
        return list(self._queue)


class MockTaskExecutor:
    """Simulated task executor for testing.

    Dispatches tasks by name to built-in mock handlers:

    * ``email_notification`` -- returns ``{"task_id": ..., "sent": True}``
    * ``data_processing`` -- returns ``{"task_id": ..., "result": <computed>}``
      (supports ``sum``/``avg`` operations; defaults to ``sum``)
    * ``cleanup_job`` -- returns ``{"task_id": ..., "cleaned": True}``
    * Any unknown task name succeeds with ``{"task_id": ..., "executed": True}``

    Example:
        ```python
        executor = MockTaskExecutor()
        result = await executor.execute_task(task)
        assert result.success
        ```
    """

    def __init__(self) -> None:
        self._executed: int = 0
        self._successful: int = 0
        self._failed: int = 0

    async def execute_task(
        self,
        task: Any,
    ) -> MockTaskResult[dict[str, Any]]:
        """Execute *task* via the appropriate mock handler.

        Args:
            task: Task object with ``id``, ``name``, ``args``, ``kwargs``.

        Returns:
            A :class:`MockTaskResult` with ``success=True`` and a ``value``
            dict, or ``success=False`` with an ``error``.
        """
        self._executed += 1
        try:
            value = await self._dispatch(task)
            self._successful += 1
            return MockTaskResult(success=True, value=value)
        except Exception as exc:  # noqa: BLE001 — any handler failure is a failed task result, never a raw raise
            self._failed += 1
            return MockTaskResult(success=False, error=str(exc))

    async def _dispatch(self, task: Any) -> dict[str, Any]:
        """Route *task* to its mock handler; raises on unrecognised operations."""
        name: str = task.name
        args: tuple[Any, ...] = task.args or ()
        kwargs: dict[str, Any] = task.kwargs or {}

        if name == "email_notification":
            return {"task_id": task.id, "sent": True}

        if name == "data_processing":
            data: list[Any] = args[0] if args else []
            operation: str = kwargs.get("operation", "sum")
            if operation == "sum":
                result: Any = sum(data)
            elif operation == "avg":
                result = sum(data) / len(data) if data else 0
            else:
                result = sum(data)
            return {"task_id": task.id, "result": result}

        if name == "cleanup_job":
            return {"task_id": task.id, "cleaned": True}

        # Generic fallback for any other task name
        return {"task_id": task.id, "executed": True}

    async def get_execution_stats(self) -> dict[str, int]:
        """Return cumulative execution statistics.

        Returns:
            A dict with ``executed``, ``successful``, and ``failed`` keys.
        """
        return {
            "executed": self._executed,
            "successful": self._successful,
            "failed": self._failed,
        }


class MockTasksProvider:
    """Lightweight provider handle returned by :meth:`TaskTestClient.start_provider`.

    Wraps the test bed's queue and executor so that tests can assert on
    provider identity (``client.provider is provider``) without a real
    framework provider lifecycle.
    """

    def __init__(
        self,
        queue: MockTaskQueue,
        executor: MockTaskExecutor,
    ) -> None:
        self.queue = queue
        self.executor = executor
        self._running: bool = True

    @property
    def is_running(self) -> bool:
        """Return whether the provider is active."""
        return self._running

    async def shutdown(self) -> None:
        """Mark the provider as stopped."""
        self._running = False

    @asynccontextmanager
    async def context(self) -> AsyncGenerator[MockTasksProvider, None]:
        """Async context manager that shuts down on exit."""
        try:
            yield self
        finally:
            await self.shutdown()


__all__ = [
    "MockTaskExecutor",
    "MockTaskQueue",
    "MockTaskResult",
    "MockTasksProvider",
]
