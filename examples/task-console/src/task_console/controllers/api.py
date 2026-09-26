"""Convention followed: **Controller pattern** — stateless HTTP adapters;
services return plain dicts or ``None``; validation failures raise
``ValueError`` mapped to a 422 by the framework.

Browser API for the Task Console demo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions.domain import NotFoundError, ValidationError
from quadkit.result import Err, Ok, Result
from quadkit.web import Controller, get, post

if TYPE_CHECKING:
    from task_console.services.console import TaskConsoleService

#: Task names the browser is allowed to enqueue — mirrors the demo's own
#: registered handler set (see ``services/handlers.py``), never an
#: arbitrary caller-supplied dotted path.
_ALLOWED_TASKS = frozenset(
    {
        "send_welcome_email",
        "resize_image",
        "flaky_report",
        "always_fails",
        "compute_digest",
        "flaky_ping",
    }
)


class TaskConsoleApiController(Controller):
    """Expose job enqueueing, result polling, worker/scheduler stats, and DLQ retry."""

    prefix = "/api/tasks"

    def __init__(self, service: TaskConsoleService | None = None) -> None:
        self._service = service

    @get("/health")
    async def health(self) -> dict[str, Any]:
        """Return the health status of the underlying task provider."""
        return await self._service.health()

    @post("")
    async def enqueue(
        self, payload: dict[str, Any]
    ) -> Result[dict[str, Any], ValidationError]:
        """Enqueue a job from ``{task, kwargs, priority, max_retries}``."""
        task_name = str(payload.get("task", ""))
        if task_name not in _ALLOWED_TASKS:
            return Err(
                ValidationError(
                    f"Unknown task {task_name!r}; must be one of {sorted(_ALLOWED_TASKS)}"
                )
            )
        kwargs = payload.get("kwargs") or {}
        if not isinstance(kwargs, dict):
            return Err(ValidationError("'kwargs' must be an object"))
        priority = int(payload.get("priority", 5))
        max_retries = int(payload.get("max_retries", 3))
        entry = await self._service.enqueue(
            task_name, kwargs=kwargs, priority=priority, max_retries=max_retries
        )
        return Ok(entry)

    @get("/submitted")
    async def submitted_jobs(self) -> dict[str, Any]:
        """List every job the demo has submitted this run, most recent first."""
        jobs = await self._service.submitted_jobs()
        return {"count": len(jobs), "jobs": jobs}

    @get("/jobs/{job_id}")
    async def get_result(self, job_id: str) -> Result[dict[str, Any], NotFoundError]:
        """Return the stored result for ``job_id``, or 404 if not yet available."""
        result = await self._service.get_result(job_id)
        if result is None:
            return Err(NotFoundError(f"No result yet for job {job_id!r}"))
        return Ok(result)

    @get("/jobs/{job_id}/wait")
    async def wait_for_result(
        self, job_id: str
    ) -> Result[dict[str, Any], NotFoundError]:
        """Wait (bounded by config) for ``job_id`` to complete, then return its result."""
        result = await self._service.wait_for_result(job_id)
        if result is None:
            return Err(NotFoundError(f"Job {job_id!r} did not complete in time"))
        return Ok(result)

    @get("/results")
    async def recent_results(self, limit: int = 20) -> dict[str, Any]:
        """Return recently completed and failed jobs from the real result store."""
        return await self._service.recent_results(limit=limit)

    @get("/workers")
    async def worker_stats(self) -> dict[str, Any]:
        """Return live worker-pool statistics."""
        return self._service.worker_stats() or {}

    @get("/scheduled")
    async def scheduled_jobs(self) -> dict[str, Any]:
        """Return the scheduler's registered cron jobs and next-run times."""
        return self._service.scheduled_jobs() or {"scheduled_jobs": []}

    @get("/dlq")
    async def dlq_entries(self, limit: int = 50) -> dict[str, Any]:
        """List permanently failed jobs sitting in the dead letter queue."""
        entries = self._service.dlq_entries(limit=limit)
        return {"count": len(entries), "entries": entries}

    @post("/dlq/{job_id}/retry")
    async def retry_dlq_job(self, job_id: str) -> Result[dict[str, Any], NotFoundError]:
        """Re-enqueue a dead-lettered job for another attempt."""
        entry = await self._service.retry_dlq_job(job_id)
        if entry is None:
            return Err(NotFoundError(f"No dead-lettered job {job_id!r}"))
        return Ok(entry)

    @post("/dlq/purge")
    async def purge_dlq(self) -> dict[str, Any]:
        """Purge every entry from the DLQ."""
        count = self._service.purge_dlq()
        return {"ok": True, "purged": count}


__all__ = ["TaskConsoleApiController"]
