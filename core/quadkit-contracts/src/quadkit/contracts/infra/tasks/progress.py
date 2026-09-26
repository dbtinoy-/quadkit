"""Progress tracking protocol and data types for long-running tasks.

Provides the cross-package contract for task progress reporting, enabling any
package (``the optional provider``, ``quadkit-web``, …) to depend on the protocol
without importing from ``quadkit-tasks`` directly.

Example:
    ```python
    from quadkit.contracts.infra.tasks.progress import (
        ProgressTrackerProtocol,
        ProgressSnapshot,
        ProgressStatus,
    )

    class ReportController:
        def __init__(self, progress: ProgressTrackerProtocol) -> None:
            self._progress = progress

        async def stream(self, task_id: str) -> AsyncIterator[ProgressSnapshot]:
            async for snap in self._progress.subscribe(task_id):
                yield snap
    ```
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class ProgressStatus(str, Enum):
    """Lifecycle states for a tracked task.

    Values are lowercase strings so they round-trip cleanly through JSON.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass(frozen=True)
class ProgressSnapshot:
    """Immutable point-in-time view of a task's progress.

    Args:
        task_id: Unique identifier for the tracked task.
        current: Number of units completed so far.
        total: Total number of units to complete (0 means unknown).
        status: Current lifecycle state.
        message: Human-readable status message.
        error: Error description when ``status`` is ``FAILED``; empty otherwise.
        metadata: JSON-safe terminal UI hints copied by tracker implementations.
    """

    task_id: str
    current: int
    total: int
    status: ProgressStatus
    message: str = ""
    error: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def percent(self) -> float:
        """Completion percentage in the range ``[0.0, 100.0]``.

        Returns ``0.0`` when ``total`` is unknown (zero).
        """
        if self.total == 0:
            return 0.0
        return min(100.0, self.current / self.total * 100)


@runtime_checkable
class ProgressTrackerProtocol(Protocol):
    """Protocol for tracking and broadcasting task progress.

    Implementations must be safe for concurrent use — multiple coroutines
    may call ``update`` on the same ``task_id`` simultaneously, and multiple
    consumers may subscribe to the same task.

    The ``subscribe`` method returns a live ``AsyncIterator`` that yields a
    new :class:`ProgressSnapshot` every time ``update``, ``complete``, or
    ``fail`` is called for the given task.  The iterator terminates
    automatically when the task reaches a terminal state (``COMPLETE`` or
    ``FAILED``).

    Example:
        ```python
        async def export_data(tracker: ProgressTrackerProtocol) -> None:
            records = await fetch_all()
            total = len(records)
            for i, record in enumerate(records, start=1):
                await process(record)
                await tracker.update("export-1", i, total, f"Row {i}/{total}")
            await tracker.complete("export-1", "Export finished")
        ```
    """

    async def update(
        self,
        task_id: str,
        current: int,
        total: int,
        message: str = "",
    ) -> None:
        """Record incremental progress for a task.

        Args:
            task_id: Unique identifier for the task.
            current: Units completed so far.
            total: Total units to process (0 = unknown).
            message: Optional human-readable status message.
        """
        ...

    async def complete(
        self,
        task_id: str,
        result: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Mark a task as successfully completed.

        Closes all active subscriptions for ``task_id`` after broadcasting the
        terminal :class:`ProgressSnapshot`.

        Args:
            task_id: Unique identifier for the task.
            result: Optional human-readable completion message.
            metadata: Optional JSON-safe terminal UI hints.
        """
        ...

    async def fail(
        self,
        task_id: str,
        error: str,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Mark a task as failed.

        Closes all active subscriptions for ``task_id`` after broadcasting the
        terminal :class:`ProgressSnapshot`.

        Args:
            task_id: Unique identifier for the task.
            error: Description of the failure.
            metadata: Optional JSON-safe terminal UI hints.
        """
        ...

    async def get(self, task_id: str) -> ProgressSnapshot | None:
        """Return the current progress state for a task.

        Args:
            task_id: Unique identifier for the task.

        Returns:
            The most recent :class:`ProgressSnapshot`, or ``None`` if the task
            is not known to this tracker.
        """
        ...

    def subscribe(self, task_id: str) -> AsyncIterator[ProgressSnapshot]:
        """Subscribe to live progress updates for a task.

        Returns an async iterator that yields a new :class:`ProgressSnapshot`
        each time the task's state changes.  The iterator stops automatically
        when the task reaches a terminal state (``COMPLETE`` or ``FAILED``).

        If the task is already in a terminal state when ``subscribe`` is
        called, the iterator yields the final snapshot once and then stops.

        Args:
            task_id: Unique identifier for the task to observe.

        Returns:
            An :class:`AsyncIterator` of :class:`ProgressSnapshot` objects.

        Example:
            ```python
            async for snap in tracker.subscribe("job-42"):
                print(f"{snap.percent:.1f}% — {snap.message}")
            ```
        """
        ...


__all__ = [
    "ProgressSnapshot",
    "ProgressStatus",
    "ProgressTrackerProtocol",
]
