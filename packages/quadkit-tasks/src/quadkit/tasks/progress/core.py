"""Real-time task progress tracking.

Enables long-running tasks to report progress with percentage,
estimated time remaining, and status messages.

Example:
    async def import_data(data, progress: ProgressTracker):
        total = len(data)
        for i, record in enumerate(data):
            await process(record)
            await progress.update(i + 1, total, f"Processing record {i + 1}")

    tracker = ProgressTracker(job_id="abc", store=InMemoryProgressStore())
    await import_data(data, tracker)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

logger = get_logger(__name__)


@dataclass
class ProgressInfo:
    """Current progress state of a task."""

    job_id: str
    current: int = 0
    total: int = 0
    percentage: float = 0.0
    message: str = ""
    started_at: float = 0.0
    updated_at: float = 0.0
    estimated_remaining_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        """Return True when the current count has reached the total."""
        return self.current >= self.total > 0

    @property
    def elapsed_seconds(self) -> float:
        """Return seconds elapsed since the task started, or 0 if not started."""
        if self.started_at == 0:
            return 0
        return ambient_clock.monotonic() - self.started_at


class ProgressStore(ABC):
    """Abstract storage for progress state."""

    @abstractmethod
    async def save(self, info: ProgressInfo) -> None:
        """Save progress state."""

    @abstractmethod
    async def get(self, job_id: str) -> ProgressInfo | None:
        """Get progress for a job."""

    @abstractmethod
    async def delete(self, job_id: str) -> None:
        """Remove progress entry."""

    @abstractmethod
    async def list_active(self) -> list[ProgressInfo]:
        """List all active (incomplete) progress entries."""


class InMemoryProgressStore(ProgressStore):
    """In-memory progress store for development/testing."""

    def __init__(self) -> None:
        self._store: dict[str, ProgressInfo] = {}

    async def save(self, info: ProgressInfo) -> None:
        """Persist a ProgressInfo entry in the in-memory store."""
        self._store[info.job_id] = info

    async def get(self, job_id: str) -> ProgressInfo | None:
        """Return the ProgressInfo for the given job ID, or None if not found."""
        return self._store.get(job_id)

    async def delete(self, job_id: str) -> None:
        """Remove the progress entry for the given job ID if it exists."""
        self._store.pop(job_id, None)

    async def list_active(self) -> list[ProgressInfo]:
        """Return all progress entries whose current count has not yet reached total."""
        return [p for p in self._store.values() if not p.is_complete]


class ProgressTracker:
    """Track and report task progress.

    Injected into task handlers to enable progress reporting.
    """

    def __init__(self, job_id: str, store: ProgressStore) -> None:
        self._info = ProgressInfo(
            job_id=job_id,
            started_at=ambient_clock.monotonic(),
        )
        self._store = store

    async def update(
        self,
        current: int,
        total: int,
        message: str = "",
        **metadata: Any,
    ) -> None:
        """Update progress.

        Args:
            current: Current progress count.
            total: Total items to process.
            message: Human-readable status message.
            **metadata: Additional metadata.
        """
        self._info.current = current
        self._info.total = total
        self._info.percentage = round(
            (current / total * 100) if total > 0 else 0,
            1,
        )
        self._info.message = message
        self._info.updated_at = ambient_clock.monotonic()
        self._info.metadata.update(metadata)

        # Estimate remaining time
        elapsed = self._info.elapsed_seconds
        if current > 0 and elapsed > 0:
            rate = current / elapsed
            remaining = total - current
            self._info.estimated_remaining_seconds = round(
                remaining / rate,
                1,
            )

        await self._store.save(self._info)

    async def complete(self, message: str = "Complete") -> None:
        """Mark progress as complete."""
        await self.update(
            self._info.total or 1,
            self._info.total or 1,
            message,
        )

    async def fail(self, message: str) -> None:
        """Mark progress as failed."""
        self._info.message = f"FAILED: {message}"
        self._info.updated_at = ambient_clock.monotonic()
        await self._store.save(self._info)

    @property
    def info(self) -> ProgressInfo:
        """Return the current ProgressInfo snapshot."""
        return self._info
