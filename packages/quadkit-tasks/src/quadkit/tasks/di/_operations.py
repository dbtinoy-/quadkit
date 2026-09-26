"""Runtime task operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.idempotency import IdempotencyStoreProtocol
from quadkit.contracts.infra.tasks import (
    IdempotencyManagerProtocol,
    IdempotentTaskManagerProtocol,
    TaskQueueProtocol,
)
from quadkit.logging import get_logger
from quadkit.tasks.decorators import unwrap_task_handler
from quadkit.tasks.di._attrs import _TaskAttrsMixin
from quadkit.tasks.exceptions import TaskRegistrationError
from quadkit.tasks.execution.manager import (
    IdempotencyManager,
    IdempotentTaskManager,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.tasks.models.job import JobProtocol
    from quadkit.tasks.scheduling.templates import JobTemplateProtocol

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level helpers (no self; keep them small and testable)
# ---------------------------------------------------------------------------


class _TaskOperationsMixin(_TaskAttrsMixin):
    """See TaskProvider."""

    def register_handler(self, task_name: str, handler: Callable[..., Any]) -> None:
        """Register a task handler.

        Args:
            task_name: Name of the task type.
            handler: Task handler function or decorated task wrapper.
        """
        normalized_handler = unwrap_task_handler(handler)
        self.registry.register(task_name, normalized_handler)
        self.refresh_worker_handlers()
        logger.info("Registered handler for task: %s", task_name)

    def build_idempotency_manager(
        self,
        storage: IdempotencyStoreProtocol,
    ) -> IdempotencyManagerProtocol:
        """Build an idempotency manager over *storage* (see contract)."""
        return IdempotencyManager(storage=storage)

    def build_idempotent_task_manager(
        self,
        queue_client: TaskQueueProtocol,
        idempotency_manager: IdempotencyManagerProtocol,
    ) -> IdempotentTaskManagerProtocol:
        """Build an idempotent task manager (see contract)."""
        return IdempotentTaskManager(
            queue_client=queue_client,
            idempotency_manager=idempotency_manager,
        )

    def register_scheduled_task(self, task_func: Any) -> None:
        """Register a decorated task function for scheduling.

        Validates that the task has required metadata (_task_name and _cron).
        Registration is atomic: if scheduling fails, the handler is rolled back.

        Args:
            task_func: Task function decorated with @scheduled

        Raises:
            TaskRegistrationError: If _task_name or _cron is missing
        """
        task_name = getattr(task_func, "_task_name", None)
        if task_name is None:
            raise TaskRegistrationError(
                f"register_scheduled_task: object {task_func!r} lacks _task_name "
                "(was @scheduled decorator applied correctly?)"
            )

        cron = getattr(task_func, "_cron", None)
        if cron is None:
            raise TaskRegistrationError(
                f"register_scheduled_task: task {task_name!r} lacks _cron — "
                "use @task() for non-scheduled handlers"
            )

        self.register_handler(task_name, task_func)
        try:
            if self.enable_scheduler:
                self.schedule_job_sync(
                    job_template=task_func.signature(), cron_expression=cron
                )
        except Exception:
            self.registry.unregister(task_name)
            self.refresh_worker_handlers()
            raise

    async def enqueue_job(self, job: JobProtocol) -> str:
        """Enqueue a job for processing"""
        await self.queue.enqueue(job)
        return job.id

    async def _enqueue_job(self, job: JobProtocol) -> None:
        """Internal method to enqueue jobs (used by scheduler)"""
        await self.enqueue_job(job)

    def schedule_job_sync(
        self,
        job_template: JobProtocol | JobTemplateProtocol,
        cron_expression: str,
        job_id: str | None = None,
    ) -> str | None:
        """Schedule a job with cron expression"""
        if self.scheduler:
            return self.scheduler.schedule_job_sync(
                job_template, cron_expression, job_id
            )
        logger.warning("Scheduler not enabled")
        return None

    def unschedule_job_sync(self, job_id: str) -> bool:
        """Remove a scheduled job"""
        if self.scheduler:
            return self.scheduler.unschedule_job_sync(job_id)
        return False

    def get_worker_stats(self) -> dict[str, Any] | None:
        """Get worker pool statistics"""
        if self.worker_pool:
            return self.worker_pool.get_pool_stats()
        return None

    def get_scheduled_jobs(self) -> dict[str, Any] | None:
        """Get scheduled jobs information"""
        if self.scheduler:
            return {
                "scheduled_jobs": [
                    {
                        "job_id": job_id,
                        "name": scheduled.job_template.name,
                        "cron": scheduled.cron_expression,
                        "next_run": scheduled.next_run,
                        "enabled": scheduled.enabled,
                    }
                    for job_id, scheduled in self.scheduler.scheduled_jobs.items()
                ],
            }
        return None

    def refresh_worker_handlers(self) -> None:
        """Refresh handler mappings in all workers.

        Call this after registering new handlers to ensure workers
        can execute jobs registered after pool creation.
        """
        if self.worker_pool:
            self.worker_pool.refresh_handlers()


__all__ = ["_TaskOperationsMixin"]
