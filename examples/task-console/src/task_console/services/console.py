"""Application adapter around Quadkit's real task-processing stack.

Convention followed: **Application service** — every operation exposed in
the browser (enqueue, inspect worker/scheduler stats, retry a dead-lettered
job) is real ``quadkit-tasks`` behavior delegated to the package-owned
``TaskProviderProtocol``, ``ResultStore``, and ``WorkerPool``; the demo only
formats results for JSON and owns its curated handler set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from quadkit.tasks.dlq.core import DeadLetterQueue, FailureRecord
from quadkit.tasks.models.job import JobProtocol, JobResult

if TYPE_CHECKING:
    from quadkit.contracts.infra.tasks import TaskProviderProtocol
    from quadkit.tasks.results.core import ResultStore
    from task_console.config import TaskConsoleConfig


def _job_result_to_dict(
    job_id: str, job_name: str, result: JobResult
) -> dict[str, Any]:
    """Render a ``JobResult`` as a JSON-friendly dict, tagged with the job it belongs to."""
    return {
        "id": result.id or job_id,
        "name": result.name or job_name,
        "success": result.success,
        "data": result.data,
        "error": result.error,
        "duration_ms": round(result.duration * 1000, 2),
        "retry_count": result.retry_count,
        "completed_at": result.completed_at,
        "failed_at": result.failed_at,
    }


def _failure_to_dict(record: FailureRecord) -> dict[str, Any]:
    """Render a DLQ ``FailureRecord`` as a JSON-friendly dict."""
    return {
        "job_id": record.job.id,
        "job_name": record.job.name,
        "args": list(record.job.args),
        "kwargs": record.job.kwargs,
        "error": record.error,
        "attempt_count": record.attempt_count,
        "failed_at": record.failed_at,
    }


class TaskConsoleService:
    """Present the package-owned task-processing stack as a small browser console.

    ``provider`` and ``result_store`` are the same objects a production app
    would resolve from the DI container — enqueueing, worker/scheduler
    inspection, and DLQ retry are genuine ``quadkit-tasks`` behavior, not
    look-alikes. The demo tracks a small "submitted job ids" list client-side
    (in-process here) because ``TaskQueueProtocol`` has no "list all jobs
    ever submitted" method — the same "demo tracks what the protocol can't
    list" pattern ``notification-center`` and ``search-console`` use.
    """

    def __init__(
        self,
        provider: TaskProviderProtocol,
        result_store: ResultStore,
        dead_letter_queue: DeadLetterQueue,
        config: TaskConsoleConfig,
    ) -> None:
        self._provider = provider
        self._result_store = result_store
        self._dlq = dead_letter_queue
        self._config = config
        self._submitted: list[dict[str, Any]] = []

    async def seed(self) -> None:
        """Enqueue a handful of sample jobs on boot, including one guaranteed to fail."""
        if not self._config.seed_demo_jobs:
            return
        await self.enqueue(
            "send_welcome_email", kwargs={"user_id": "u-1", "email": "u1@example.com"}
        )
        await self.enqueue(
            "resize_image", kwargs={"image_id": "img-42", "width": 1024, "height": 768}
        )
        await self.enqueue("flaky_report", kwargs={"report_id": "rpt-boot"})
        await self.enqueue("always_fails", kwargs={"reason": "seeded DLQ example"})

    async def enqueue(
        self,
        task_name: str,
        kwargs: dict[str, Any] | None = None,
        *,
        priority: int = 5,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """Enqueue a real job through ``TaskProviderProtocol.enqueue_job()``."""
        job = JobProtocol(
            id="",
            name=task_name,
            kwargs=kwargs or {},
            priority=priority,
            max_retries=max_retries,
        )
        job_id = await self._provider.enqueue_job(job)
        entry = {
            "id": job_id,
            "name": task_name,
            "kwargs": kwargs or {},
            "priority": priority,
            "max_retries": max_retries,
        }
        self._submitted.append(entry)
        return entry

    async def submitted_jobs(self) -> list[dict[str, Any]]:
        """Return every job the demo has submitted this run, most recent first."""
        return list(reversed(self._submitted))

    async def get_result(self, job_id: str) -> dict[str, Any] | None:
        """Return the stored result for ``job_id``, or ``None`` if not yet available."""
        result = await self._result_store.get(job_id)
        if result is None:
            return None
        return _job_result_to_dict(job_id, result.name or "", result)

    async def wait_for_result(self, job_id: str) -> dict[str, Any] | None:
        """Wait (bounded by config) for ``job_id`` to complete, then return its result."""
        result = await self._result_store.wait(
            job_id, timeout=self._config.poll_wait_seconds
        )
        if result is None:
            return None
        return _job_result_to_dict(job_id, result.name or "", result)

    async def recent_results(self, limit: int = 20) -> dict[str, Any]:
        """Return recently completed and failed jobs from the real result store."""
        completed = await self._result_store.get_completed(limit=limit)
        failed = await self._result_store.get_failed(limit=limit)
        return {
            "completed": [
                _job_result_to_dict(r.id or "", r.name or "", r) for r in completed
            ],
            "failed": [
                _job_result_to_dict(r.id or "", r.name or "", r) for r in failed
            ],
        }

    def worker_stats(self) -> dict[str, Any] | None:
        """Return live worker-pool statistics from the real ``WorkerPool``."""
        return self._provider.get_worker_stats()

    def scheduled_jobs(self) -> dict[str, Any] | None:
        """Return the scheduler's registered cron jobs and next-run times."""
        return self._provider.get_scheduled_jobs()

    def dlq_entries(self, limit: int = 50) -> list[dict[str, Any]]:
        """List permanently failed jobs sitting in the real ``DeadLetterQueue``."""
        return [_failure_to_dict(r) for r in self._dlq.list_failed(limit=limit)]

    async def retry_dlq_job(self, job_id: str) -> dict[str, Any] | None:
        """Pop ``job_id`` out of the DLQ and re-enqueue it for another attempt.

        ``DeadLetterQueue.retry()`` resets the job's status/result but keeps
        its original id, and ``JobProtocol`` only generates a fresh id in
        ``__post_init__`` (i.e. at construction) — assigning an empty string
        afterwards does *not* regenerate one. Re-enqueuing under the same id
        would silently overwrite the original result-store entry, so a new
        id is assigned explicitly here.
        """
        job = self._dlq.retry(job_id)
        if job is None:
            return None
        job.id = str(uuid.uuid4())
        new_id = await self._provider.enqueue_job(job)
        entry = {
            "id": new_id,
            "name": job.name,
            "kwargs": job.kwargs,
            "retried_from": job_id,
        }
        self._submitted.append(entry)
        return entry

    def purge_dlq(self) -> int:
        """Purge every entry from the DLQ regardless of age; returns the count removed.

        ``DeadLetterQueue.purge()`` only removes records older than
        ``older_than_hours`` — and since ``0`` is falsy, calling it with
        ``older_than_hours=0`` silently falls back to the default 7-day
        retention window instead of purging everything. ``clear()`` is the
        real "remove every entry unconditionally" operation.
        """
        return self._dlq.clear()

    async def health(self) -> dict[str, Any]:
        """Report readiness: task provider health plus queue/DLQ counts."""
        result = await self._provider.health_check()
        return {
            "status": result.status.value,
            "details": {
                **(result.details or {}),
                "submitted_count": len(self._submitted),
                "dlq_count": len(self._dlq.list_failed(limit=10_000)),
            },
        }


__all__ = ["TaskConsoleService"]
