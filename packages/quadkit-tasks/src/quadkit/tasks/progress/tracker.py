"""In-memory implementation of :class:`ProgressTrackerProtocol`.

Provides a single-process tracker backed by ``asyncio.Queue`` objects so that
multiple coroutines can subscribe to live progress updates for any tracked
task.  All state is held in memory and is lost on process restart — use a
cache-backed or database-backed implementation for persistence across workers.

Example:
    ```python
    from quadkit.tasks.progress import InMemoryProgressTracker

    tracker = InMemoryProgressTracker()

    async def worker(task_id: str) -> None:
        for i in range(1, 6):
            await asyncio.sleep(0.1)
            await tracker.update(task_id, i, 5, f"Step {i}/5")
        await tracker.complete(task_id, "Done")

    async def monitor(task_id: str) -> None:
        async for snap in tracker.subscribe(task_id):
            print(f"{snap.percent:.0f}% — {snap.message}")

    asyncio.gather(worker("job-1"), monitor("job-1"))
    ```
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Mapping
from typing import Any

from quadkit.contracts.infra.tasks.progress import (
    ProgressSnapshot,
    ProgressStatus,
    ProgressTrackerProtocol,
)
from quadkit.logging import get_logger

logger = get_logger(__name__)

# Sentinel value used to signal subscriber queues that a task has reached a
# terminal state.  Using ``object()`` avoids any accidental equality match.
_CLOSE: Any = object()

# Type alias for the per-task subscriber queue element.
_QueueItem = ProgressSnapshot | object


class InMemoryProgressTracker:
    """Thread-safe, in-memory :class:`ProgressTrackerProtocol` implementation.

    Maintains the latest :class:`ProgressSnapshot` for each tracked task and
    fans out every state change to all active subscribers via
    ``asyncio.Queue``.

    Subscriptions are kept alive until the task reaches a terminal state
    (``COMPLETE`` or ``FAILED``), at which point the iterator closes
    automatically.  Subscribers that call :meth:`subscribe` after the task has
    already finished receive the terminal snapshot once and then stop.

    All public methods are safe to call concurrently from multiple coroutines.
    """

    def __init__(self) -> None:
        # Most-recent snapshot for each task_id.
        self._snapshots: dict[str, ProgressSnapshot] = {}
        # Active subscriber queues per task_id.
        self._subscribers: dict[str, list[asyncio.Queue[_QueueItem]]] = {}

    # ------------------------------------------------------------------
    # ProgressTrackerProtocol implementation
    # ------------------------------------------------------------------

    async def update(
        self,
        task_id: str,
        current: int,
        total: int,
        message: str = "",
    ) -> None:
        """Record incremental progress and broadcast to all subscribers.

        Args:
            task_id: Unique identifier for the task.
            current: Units completed so far.
            total: Total units to process (0 means unknown).
            message: Optional human-readable status line.
        """
        snapshot = ProgressSnapshot(
            task_id=task_id,
            current=current,
            total=total,
            status=ProgressStatus.RUNNING,
            message=message,
        )
        await self._broadcast(task_id, snapshot, close=False)
        logger.debug(
            "tasks.progress.update",
            task_id=task_id,
            current=current,
            total=total,
            percent=snapshot.percent,
        )

    async def complete(
        self,
        task_id: str,
        result: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Mark a task as successfully completed and close all subscriptions.

        Args:
            task_id: Unique identifier for the task.
            result: Optional human-readable completion message.
            metadata: Optional JSON-safe terminal UI hints.
        """
        existing = self._snapshots.get(task_id)
        total = existing.total if existing is not None else 0
        snapshot = ProgressSnapshot(
            task_id=task_id,
            current=total,
            total=total,
            status=ProgressStatus.COMPLETE,
            message=result,
            metadata=dict(metadata or {}),
        )
        await self._broadcast(task_id, snapshot, close=True)
        logger.debug("tasks.progress.complete", task_id=task_id)

    async def fail(
        self,
        task_id: str,
        error: str,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Mark a task as failed and close all subscriptions.

        Args:
            task_id: Unique identifier for the task.
            error: Description of the failure.
            metadata: Optional JSON-safe terminal UI hints.
        """
        existing = self._snapshots.get(task_id)
        snapshot = ProgressSnapshot(
            task_id=task_id,
            current=existing.current if existing is not None else 0,
            total=existing.total if existing is not None else 0,
            status=ProgressStatus.FAILED,
            error=error,
            metadata=dict(metadata or {}),
        )
        await self._broadcast(task_id, snapshot, close=True)
        logger.debug("tasks.progress.fail", task_id=task_id, error=error)

    async def get(self, task_id: str) -> ProgressSnapshot | None:
        """Return the current progress state for a task.

        Args:
            task_id: Unique identifier for the task.

        Returns:
            The most recent :class:`ProgressSnapshot`, or ``None`` if the task
            has not been seen by this tracker.
        """
        return self._snapshots.get(task_id)

    def subscribe(self, task_id: str) -> AsyncGenerator[ProgressSnapshot, None]:
        """Subscribe to live progress updates for a task.

        Returns an async generator that yields one :class:`ProgressSnapshot`
        per state change.  The generator stops automatically when the task
        reaches a terminal state.  If the task is already finished, the
        terminal snapshot is yielded once and the generator stops immediately.

        Args:
            task_id: Unique identifier for the task to observe.

        Returns:
            An async generator of :class:`ProgressSnapshot` objects.
        """
        return self._iter_snapshots(task_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _broadcast(
        self,
        task_id: str,
        snapshot: ProgressSnapshot,
        *,
        close: bool,
    ) -> None:
        """Store snapshot and push it (plus an optional sentinel) to all queues."""
        self._snapshots[task_id] = snapshot
        queues = self._subscribers.get(task_id, [])
        for queue in queues:
            await queue.put(snapshot)
            if close:
                await queue.put(_CLOSE)

    async def _iter_snapshots(
        self,
        task_id: str,
    ) -> AsyncGenerator[ProgressSnapshot, None]:
        """Async generator that yields snapshots until terminal state."""
        # If the task is already in a terminal state, yield the cached
        # snapshot once and stop — no need to register a subscriber queue.
        existing = self._snapshots.get(task_id)
        if existing is not None and existing.status in (
            ProgressStatus.COMPLETE,
            ProgressStatus.FAILED,
        ):
            yield existing
            return

        queue: asyncio.Queue[_QueueItem] = asyncio.Queue()
        self._subscribers.setdefault(task_id, []).append(queue)

        try:
            while True:
                item = await queue.get()
                if item is _CLOSE:
                    break
                # item is always a ProgressSnapshot here; the only non-snapshot
                # value placed on the queue is the _CLOSE sentinel.
                yield item  # type: ignore[misc]
        finally:
            # Always clean up the subscriber entry to prevent memory leaks,
            # even if the consumer breaks out of the loop early.
            try:
                self._subscribers[task_id].remove(queue)
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]
            except (KeyError, ValueError):
                pass


# Verify protocol conformance at import time (cheap structural check).
def _assert_protocol_conformance() -> None:
    assert isinstance(InMemoryProgressTracker(), ProgressTrackerProtocol)  # noqa: S101  # import-time protocol conformance


_assert_protocol_conformance()

__all__ = ["InMemoryProgressTracker"]
