"""Dead Letter Queue management for failed tasks.

Provides tools to inspect, retry, and purge failed jobs that
have exhausted their retry attempts.

Example:
    dlq = DeadLetterQueue(max_size=10000)

    # Worker sends failed job to DLQ
    dlq.add(job, error="Connection timeout", traceback="...")

    # Admin inspects failures
    failures = dlq.list_failed(limit=20)

    # Retry specific failure
    job = dlq.retry("job-id-123")

    # Purge old failures
    purged = dlq.purge(older_than_hours=48)
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
import time
from typing import Any

from quadkit.contracts.infra.tasks import JobStatus
from quadkit.logging import get_logger
from quadkit.tasks.models.job import JobProtocol

logger = get_logger(__name__)


@dataclass
class FailureRecord:
    """Record of a failed job in the DLQ."""

    job: JobProtocol
    error: str
    traceback: str | None = None
    failed_at: float = field(default_factory=time.time)
    attempt_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the failure record to a plain dictionary."""
        return {
            "job_id": self.job.id,
            "job_name": self.job.name,
            "job_args": list(self.job.args),
            "job_kwargs": self.job.kwargs,
            "job_priority": self.job.priority,
            "job_max_retries": self.job.max_retries,
            "job_timeout": self.job.timeout,
            "error": self.error,
            "traceback": self.traceback,
            "failed_at": self.failed_at,
            "attempt_count": self.attempt_count,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FailureRecord:
        """Deserialize a failure record from a plain dictionary.

        Args:
            data: Dictionary as produced by :meth:`to_dict`.

        Returns:
            Reconstructed :class:`FailureRecord`.
        """
        job = JobProtocol(
            id=data["job_id"],
            name=data["job_name"],
            args=tuple(data.get("job_args", [])),
            kwargs=data.get("job_kwargs", {}),
            priority=data.get("job_priority", 0),
            max_retries=data.get("job_max_retries", 3),
            timeout=data.get("job_timeout"),
            status=JobStatus.FAILED,
        )
        return cls(
            job=job,
            error=data["error"],
            traceback=data.get("traceback"),
            failed_at=data.get("failed_at", time.time()),
            attempt_count=data.get("attempt_count", 0),
            metadata=data.get("metadata", {}),
        )


class DeadLetterQueue:
    """Manages failed jobs for inspection, retry, and cleanup."""

    def __init__(
        self,
        *,
        max_size: int = 10000,
        retention_hours: float = 168,  # 7 days
    ) -> None:
        self._failures: OrderedDict[str, FailureRecord] = OrderedDict()
        self._max_size = max_size
        self._retention_hours = retention_hours
        self._total_added = 0
        self._total_retried = 0
        self._total_purged = 0

    def add(
        self,
        job: JobProtocol,
        error: str,
        traceback: str | None = None,
        **metadata: Any,
    ) -> None:
        """Add a failed job to the DLQ.

        Args:
            job: The failed job.
            error: Error message.
            traceback: Full traceback string.
            **metadata: Additional metadata.
        """
        # Evict oldest if at capacity
        while len(self._failures) >= self._max_size:
            evicted_id, _ = self._failures.popitem(last=False)
            logger.debug("DLQ evicted oldest entry: %s", evicted_id)

        self._failures[job.id] = FailureRecord(
            job=job,
            error=error,
            traceback=traceback,
            attempt_count=job.retry_count,
            metadata=metadata,
        )
        self._total_added += 1
        logger.info(
            "DLQ: added job %s (%s): %s",
            job.id,
            job.name,
            error[:100],
        )

    def get(self, job_id: str) -> FailureRecord | None:
        """Get a specific failure record."""
        return self._failures.get(job_id)

    def list_failed(
        self,
        *,
        limit: int = 50,
        job_name: str | None = None,
    ) -> list[FailureRecord]:
        """List failed jobs, optionally filtered by job name.

        Args:
            limit: Maximum records to return.
            job_name: Filter by job type name.

        Returns:
            List of failure records (newest first).
        """
        records = list(reversed(self._failures.values()))
        if job_name:
            records = [r for r in records if r.job.name == job_name]
        return records[:limit]

    def retry(self, job_id: str) -> JobProtocol | None:
        """Remove a job from DLQ and prepare it for retry.

        Returns the job with status reset to PENDING, or None
        if not found.
        """
        record = self._failures.pop(job_id, None)
        if record is None:
            return None

        job = record.job
        job.status = JobStatus.PENDING
        job.retry_count = 0
        job.last_error = None
        job.started_at = None
        job.completed_at = None
        job.result = None
        self._total_retried += 1
        logger.info("DLQ: retrying job %s (%s)", job.id, job.name)
        return job

    def retry_all(self) -> list[JobProtocol]:
        """Retry all failed jobs. Returns list of jobs to re-enqueue."""
        jobs = []
        for job_id in list(self._failures.keys()):
            job = self.retry(job_id)
            if job:
                jobs.append(job)
        return jobs

    def remove(self, job_id: str) -> bool:
        """Permanently remove a failure from the DLQ."""
        record = self._failures.pop(job_id, None)
        return record is not None

    def purge(self, *, older_than_hours: float | None = None) -> int:
        """Purge old failures.

        Args:
            older_than_hours: Remove records older than this. Defaults to
                retention_hours.

        Returns:
            Number of records purged.
        """
        cutoff_hours = older_than_hours or self._retention_hours
        cutoff = time.time() - (cutoff_hours * 3600)
        to_remove = [
            job_id
            for job_id, record in self._failures.items()
            if record.failed_at < cutoff
        ]
        for job_id in to_remove:
            del self._failures[job_id]
        self._total_purged += len(to_remove)
        if to_remove:
            logger.info("DLQ: purged %d old records", len(to_remove))
        return len(to_remove)

    def clear(self) -> int:
        """Clear all DLQ entries. Returns count cleared."""
        count = len(self._failures)
        self._failures.clear()
        return count

    @property
    def size(self) -> int:
        """Return the number of currently tracked failure records."""
        return len(self._failures)

    def get_stats(self) -> dict[str, Any]:
        """Get DLQ statistics."""
        by_name: dict[str, int] = {}
        for record in self._failures.values():
            by_name[record.job.name] = by_name.get(record.job.name, 0) + 1

        return {
            "current_size": len(self._failures),
            "max_size": self._max_size,
            "total_added": self._total_added,
            "total_retried": self._total_retried,
            "total_purged": self._total_purged,
            "by_job_type": by_name,
        }
