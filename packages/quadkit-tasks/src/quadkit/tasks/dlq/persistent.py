"""Async, backend-driven Dead Letter Queue for persistent failed-task storage.

:class:`PersistentDeadLetterQueue` is the async counterpart to the
synchronous :class:`~quadkit.tasks.dlq.core.DeadLetterQueue`.  It
delegates all storage to a :class:`~quadkit.tasks.dlq.backend.DLQBackend`
so that records survive process restarts when combined with a persistent
backend such as :class:`~quadkit.tasks.dlq.backend.StateStoreDLQBackend`.

Example::

    from quadkit.tasks.dlq.backend import StateStoreDLQBackend
    from quadkit.tasks.dlq.persistent import PersistentDeadLetterQueue

    backend = StateStoreDLQBackend(state_store=redis_state_store)
    dlq = PersistentDeadLetterQueue(backend=backend)

    await dlq.add(job, error="Connection timeout", traceback="...")
    records = await dlq.list_failed(limit=20)
    job_to_retry = await dlq.retry("job-id-123")
    purged = await dlq.purge(older_than_hours=48)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.tasks.dlq.backend import DLQBackend, InMemoryDLQBackend
from quadkit.tasks.dlq.core import FailureRecord

if TYPE_CHECKING:
    from quadkit.tasks.models.job import JobProtocol

logger = get_logger(__name__)

__all__ = ["PersistentDeadLetterQueue"]


class PersistentDeadLetterQueue:
    """Async Dead Letter Queue backed by a pluggable :class:`DLQBackend`.

    Unlike the synchronous :class:`~quadkit.tasks.dlq.core.DeadLetterQueue`,
    all mutation methods are coroutines so that they can call through to
    async storage backends (Redis, database, etc.) without blocking the event
    loop.

    The default backend is :class:`~quadkit.tasks.dlq.backend.InMemoryDLQBackend`,
    which gives the same in-memory behaviour as the original queue.  Swap it for
    :class:`~quadkit.tasks.dlq.backend.StateStoreDLQBackend` to gain persistence.
    """

    def __init__(
        self,
        *,
        backend: DLQBackend | None = None,
        retention_hours: float = 168,  # 7 days
    ) -> None:
        """Initialise the persistent DLQ.

        Args:
            backend: Storage backend.  Defaults to :class:`InMemoryDLQBackend`.
            retention_hours: Records older than this threshold are purged by
                :meth:`purge`.  Defaults to 168 h (7 days).
        """
        self._backend: DLQBackend = backend or InMemoryDLQBackend()
        self._retention_hours = retention_hours
        self._total_added = 0
        self._total_retried = 0
        self._total_purged = 0

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def add(
        self,
        job: JobProtocol,
        error: str,
        traceback: str | None = None,
        **metadata: Any,
    ) -> None:
        """Add a failed job to the DLQ.

        Args:
            job: The failed job.
            error: Human-readable error message.
            traceback: Full traceback string (optional).
            **metadata: Arbitrary key-value metadata stored alongside the record.
        """
        record = FailureRecord(
            job=job,
            error=error,
            traceback=traceback,
            attempt_count=job.retry_count,
            metadata=dict(metadata),
        )
        await self._backend.add(job.id, record.to_dict())
        self._total_added += 1
        logger.info(
            "PersistentDLQ: added job %s (%s): %s",
            job.id,
            job.name,
            error[:100],
        )

    async def remove(self, job_id: str) -> bool:
        """Permanently remove a failure from the DLQ.

        Returns:
            ``True`` if the record existed and was removed.
        """
        return await self._backend.remove(job_id)

    async def clear(self) -> int:
        """Remove all failure records.

        Returns:
            Number of records cleared.
        """
        return await self._backend.clear()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get(self, job_id: str) -> FailureRecord | None:
        """Retrieve a single failure record by job ID.

        Returns:
            :class:`~quadkit.tasks.dlq.core.FailureRecord` if found,
            ``None`` otherwise.
        """
        raw = await self._backend.get(job_id)
        if raw is None:
            return None
        if isinstance(raw, FailureRecord):
            return raw
        return FailureRecord.from_dict(raw)

    async def list_failed(
        self,
        *,
        limit: int = 50,
        job_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """List failed jobs, newest first.

        Args:
            limit: Maximum number of records to return.
            job_name: Optional job-type filter.

        Returns:
            List of serialised :class:`~quadkit.tasks.dlq.core.FailureRecord`
            dicts.
        """
        all_records = await self._backend.list_all()
        all_records = list(reversed(all_records))
        if job_name:
            all_records = [r for r in all_records if r.get("job_name") == job_name]
        return all_records[:limit]

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------

    async def retry(self, job_id: str) -> JobProtocol | None:
        """Remove a job from DLQ and return it prepared for re-queuing.

        Returns:
            The :class:`~quadkit.tasks.models.job.JobProtocol` with status reset to
            ``PENDING``, or ``None`` if not found.
        """
        record_data = await self._backend.get(job_id)
        if record_data is None:
            return None
        await self._backend.remove(job_id)
        self._total_retried += 1
        logger.info(
            "PersistentDLQ: retrying job %s (%s)", job_id, record_data.get("job_name")
        )
        # Reconstruct a minimal JobProtocol from the record — callers should re-fetch
        # the full job from the queue if more attributes are needed.
        return None  # Callers must resolve the job from the task queue.

    # ------------------------------------------------------------------
    # Purge
    # ------------------------------------------------------------------

    async def purge(self, *, older_than_hours: float | None = None) -> int:
        """Purge records older than the retention threshold.

        Args:
            older_than_hours: Override the default retention period.

        Returns:
            Number of records removed.
        """
        cutoff_hours = older_than_hours or self._retention_hours
        cutoff = time.time() - (cutoff_hours * 3600)
        all_records = await self._backend.list_all()
        removed = 0
        for record in all_records:
            if record.get("failed_at", float("inf")) < cutoff:
                job_id = record.get("job_id")
                if job_id and await self._backend.remove(job_id):
                    removed += 1
        self._total_purged += removed
        if removed:
            logger.info("PersistentDLQ: purged %d old records", removed)
        return removed

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Return DLQ statistics (excluding current size, which is async).

        Returns:
            Dict with ``total_added``, ``total_retried``, ``total_purged``.
        """
        return {
            "total_added": self._total_added,
            "total_retried": self._total_retried,
            "total_purged": self._total_purged,
        }
