"""Task result store for persisting and querying results.

Enables the `await task.result()` pattern by storing job results
with TTL-based expiry.

Example:
    store = InMemoryResultStore(ttl=3600)

    # Worker stores result
    await store.store("job-123", JobResult.ok(data={"user_id": 42}))

    # Client retrieves result
    result = await store.get("job-123")

    # Or wait for result with timeout
    result = await store.wait("job-456", timeout=30.0)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections import OrderedDict
from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.tasks.models.job import JobResult

logger = get_logger(__name__)


class ResultStore(ABC):
    """Abstract result store backend."""

    @abstractmethod
    async def store(self, job_id: str, result: JobResult) -> None:
        """Store a job result."""

    @abstractmethod
    async def get(self, job_id: str) -> JobResult | None:
        """Get a result by job ID. Returns None if not found or expired."""

    @abstractmethod
    async def delete(self, job_id: str) -> bool:
        """Delete a result. Returns True if deleted."""

    @abstractmethod
    async def wait(
        self,
        job_id: str,
        *,
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> JobResult | None:
        """Wait for a result with timeout."""

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Remove expired results. Returns count removed."""

    async def get_completed(self, limit: int | None = None) -> list[JobResult]:
        """Return recently completed job results, newest first.

        Backends that can enumerate stored results should override this;
        the default implementation returns an empty list.

        Args:
            limit: Maximum number of results to return; ``None`` for all.

        Returns:
            Completed job results, newest first.
        """
        return []

    async def get_failed(self, limit: int | None = None) -> list[JobResult]:
        """Return recently failed job results, newest first.

        Backends that can enumerate stored results should override this;
        the default implementation returns an empty list.

        Args:
            limit: Maximum number of results to return; ``None`` for all.

        Returns:
            Failed job results, newest first.
        """
        return []


@dataclass
class _ResultEntry:
    result: JobResult
    stored_at: float
    ttl: int
    event: asyncio.Event = field(default_factory=asyncio.Event)


class InMemoryResultStore(ResultStore):
    """In-memory result store with TTL-based expiry.

    Suitable for development and single-process deployments.
    For production, implement a Redis-backed store.
    """

    def __init__(
        self,
        *,
        ttl: int = 3600,
        max_size: int = 10000,
    ) -> None:
        self._results: OrderedDict[str, _ResultEntry] = OrderedDict()
        self._pending: dict[str, asyncio.Event] = {}
        self._ttl = ttl
        self._max_size = max_size
        self._total_stored = 0

    async def store(self, job_id: str, result: JobResult) -> None:
        """Persist a job result, evicting the oldest entry when at capacity."""
        # Evict if at capacity
        while len(self._results) >= self._max_size:
            self._results.popitem(last=False)

        event = self._pending.pop(job_id, asyncio.Event())
        self._results[job_id] = _ResultEntry(
            result=result,
            stored_at=time.monotonic(),
            ttl=self._ttl,
            event=event,
        )
        event.set()  # Wake up anyone waiting
        self._total_stored += 1

    async def get(self, job_id: str) -> JobResult | None:
        """Return the result for the given job ID, or None if absent or expired."""
        entry = self._results.get(job_id)
        if entry is None:
            return None

        # Check expiry
        if time.monotonic() - entry.stored_at > entry.ttl:
            del self._results[job_id]
            return None

        return entry.result

    async def delete(self, job_id: str) -> bool:
        """Remove the result for the given job ID and return True if it existed."""
        entry = self._results.pop(job_id, None)
        return entry is not None

    async def wait(
        self,
        job_id: str,
        *,
        timeout: float = 30.0,
        poll_interval: float = 0.5,
    ) -> JobResult | None:
        """Wait for a result to appear, with timeout."""
        # Check if already available
        existing = await self.get(job_id)
        if existing is not None:
            return existing

        # Create event for this job
        event = self._pending.setdefault(job_id, asyncio.Event())

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return await self.get(job_id)
        except TimeoutError:
            self._pending.pop(job_id, None)
            return None

    async def cleanup_expired(self) -> int:
        """Remove all entries whose TTL has elapsed and return the count removed."""
        now = time.monotonic()
        expired_keys = [
            job_id
            for job_id, entry in self._results.items()
            if now - entry.stored_at > entry.ttl
        ]
        for key in expired_keys:
            del self._results[key]
        return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Return store statistics including size, capacity, and waiter count."""
        return {
            "stored": len(self._results),
            "max_size": self._max_size,
            "pending_waiters": len(self._pending),
            "total_stored": self._total_stored,
            "ttl": self._ttl,
        }

    async def get_completed(self, limit: int | None = None) -> list[JobResult]:
        """Return the most recently completed results, newest first.

        Args:
            limit: Maximum number of results to return; ``None`` for all.

        Returns:
            Successful stored results, newest first.
        """
        now = time.monotonic()
        completed = [
            entry.result
            for entry in self._results.values()
            if now - entry.stored_at <= entry.ttl and entry.result.success
        ]
        return completed[::-1][:limit]

    async def get_failed(self, limit: int | None = None) -> list[JobResult]:
        """Return the most recently failed results, newest first.

        Args:
            limit: Maximum number of results to return; ``None`` for all.

        Returns:
            Failed stored results, newest first.
        """
        now = time.monotonic()
        failed = [
            entry.result
            for entry in self._results.values()
            if now - entry.stored_at <= entry.ttl and not entry.result.success
        ]
        return failed[::-1][:limit]
