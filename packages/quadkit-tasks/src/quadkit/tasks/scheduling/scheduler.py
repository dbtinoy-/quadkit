"""Task scheduler for cron-like job scheduling

This module provides the TaskScheduler for managing scheduled jobs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.tasks.models.job import JobProtocol
from quadkit.tasks.scheduling.cron import CronExpression
from quadkit.tasks.scheduling.dependency_resolver import DependencyResolver
from quadkit.tasks.scheduling.templates import JobTemplateProtocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.tasks.scheduling.persistence import SchedulerStore

logger = get_logger(__name__)


@dataclass
class ScheduledJob:
    """Represents a scheduled job with cron expression

    Attributes:
        job_template: Template for creating job instances
        cron_expression: Cron expression string
        next_run: Unix timestamp of next execution
        enabled: Whether job is enabled for execution
    """

    job_template: JobTemplateProtocol
    cron_expression: str
    next_run: float
    enabled: bool = True

    def calculate_next_run(self) -> float:
        """Calculate the next run time based on cron expression

        Returns:
            Unix timestamp of next execution
        """
        cron = CronExpression(self.cron_expression)
        return cron.get_next()


class TaskScheduler:
    """Task scheduler for cron-like job scheduling

    TaskScheduler manages periodic job execution using cron expressions.
    Jobs are checked at regular intervals and enqueued when due.

    Example:
        ```python
        scheduler = TaskScheduler()

        # Schedule job
        template = JobTemplateProtocol(name="cleanup", args=())
        scheduler.schedule_job(template, "0 0 * * *")  # Daily at midnight

        # Start scheduler
        await scheduler.start_scheduler(queue.enqueue)
        ```
    """

    def __init__(
        self,
        check_interval: float = 60.0,
        store: SchedulerStore | None = None,
    ):
        """Initialize task scheduler.

        Args:
            check_interval: How often to check for due jobs (seconds).
            store: Optional :class:`~quadkit.tasks.scheduling.persistence.SchedulerStore`
                for durable persistence of job definitions and next-run times.
                When provided, all schedule/unschedule operations are persisted
                and the scheduler can be restored after restart via
                :meth:`restore_from_store`.
        """
        self.scheduled_jobs: dict[str, ScheduledJob] = {}
        self.running = False
        self.check_interval = check_interval
        self._dependency_resolver: DependencyResolver = DependencyResolver()
        self._store: SchedulerStore | None = store

    def schedule_job_sync(
        self,
        job_template: JobTemplateProtocol | JobProtocol,
        cron_expression: str,
        job_id: str | None = None,
    ) -> str:
        """Schedule a job with cron expression (sync, no persistence).

        For the primary async version with store persistence, use
        :meth:`schedule_job`.

        Args:
            job_template: JobProtocol template or JobProtocol to schedule
            cron_expression: Cron expression (e.g., "0 9 * * 1-5")
            job_id: Optional job ID, generated if not provided

        Returns:
            JobProtocol ID for the scheduled job
        """
        # Convert JobProtocol to JobTemplateProtocol if needed
        if isinstance(job_template, JobProtocol):
            template = JobTemplateProtocol.from_job(job_template)
        else:
            template = job_template

        if job_id is None:
            job_id = f"scheduled_{template.name}_{int(time.time())}"

        # Calculate first run time
        cron = CronExpression(cron_expression)
        next_run = cron.get_next()

        scheduled_job = ScheduledJob(
            job_template=template,
            cron_expression=cron_expression,
            next_run=next_run,
            enabled=True,
        )

        # Validate dependency graph before committing the job.  Raises
        # TaskDependencyCycleError if adding these edges creates a cycle.
        if template.depends_on:
            self._dependency_resolver.register(job_id, template.depends_on)

        self.scheduled_jobs[job_id] = scheduled_job
        logger.info("Scheduled job %s with cron: %s", job_id, cron_expression)
        return job_id

    async def schedule_job(
        self,
        job_template: JobTemplateProtocol | JobProtocol,
        cron_expression: str,
        job_id: str | None = None,
    ) -> str:
        """Schedule a job and persist to store if one is configured.

        This is the primary async method.  For a synchronous variant
        without persistence, use :meth:`schedule_job_sync`.

        Args:
            job_template: JobProtocol template or JobProtocol to schedule.
            cron_expression: Cron expression (e.g., ``"0 9 * * 1-5"``).
            job_id: Optional job ID, generated if not provided.

        Returns:
            JobProtocol ID for the scheduled job.
        """
        job_id = self.schedule_job_sync(job_template, cron_expression, job_id)
        if self._store:
            await self._store.save_job(job_id, self.scheduled_jobs[job_id])
        return job_id

    async def restore_from_store(self) -> int:
        """Restore all persisted job definitions from the configured store.

        Loads every job persisted by previous scheduler instances and re-registers
        them in :attr:`scheduled_jobs`.  Call this once during startup before
        invoking :meth:`start_scheduler` to resume the full scheduling state.

        Returns:
            Number of jobs restored.

        Raises:
            RuntimeError: If no :class:`~quadkit.tasks.scheduling.persistence.SchedulerStore`
                was provided at construction.
        """
        if self._store is None:
            msg = "Cannot restore: no SchedulerStore configured"
            raise RuntimeError(msg)
        persisted = await self._store.load_jobs()
        for job_id, job in persisted.items():
            self.scheduled_jobs[job_id] = job
            if job.job_template.depends_on:
                self._dependency_resolver.register(job_id, job.job_template.depends_on)
        logger.info("scheduler.restored", count=len(persisted))
        return len(persisted)

    def unschedule_job_sync(self, job_id: str) -> bool:
        """Remove a scheduled job (sync, no store deletion).

        For the primary async version with store deletion, use
        :meth:`unschedule_job`.

        Args:
            job_id: JobProtocol ID to remove

        Returns:
            True if job was removed, False if not found
        """
        if job_id in self.scheduled_jobs:
            del self.scheduled_jobs[job_id]
            self._dependency_resolver.remove(job_id)
            logger.info("Unscheduled job %s", job_id)
            return True
        return False

    async def unschedule_job(self, job_id: str) -> bool:
        """Remove a scheduled job and delete it from the store.

        This is the primary async method.  For a synchronous variant
        without store deletion, use :meth:`unschedule_job_sync`.

        Args:
            job_id: JobProtocol ID to remove.

        Returns:
            True if job was removed, False if not found.
        """
        removed = self.unschedule_job_sync(job_id)
        if removed and self._store:
            await self._store.delete_job(job_id)
        return removed

    def get_scheduled_jobs(self) -> list[ScheduledJob]:
        """Get all scheduled jobs

        Returns:
            List of all scheduled jobs
        """
        return list(self.scheduled_jobs.values())

    def get_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        """Get a specific scheduled job

        Args:
            job_id: JobProtocol ID

        Returns:
            ScheduledJob or None if not found
        """
        return self.scheduled_jobs.get(job_id)

    async def start_scheduler(
        self, enqueue_callback: Callable[[JobProtocol], Any]
    ) -> None:
        """Start the scheduler loop

        Args:
            enqueue_callback: Async function to enqueue jobs when they are due
        """
        self.running = True
        logger.info("Task scheduler started")

        while self.running:
            try:
                await self._check_scheduled_jobs(enqueue_callback)
                await asyncio.sleep(self.check_interval)
            except Exception:  # noqa: BLE001 — resilience boundary
                # Intentionally broad: scheduler loop must not exit on unexpected errors.
                logger.exception("Scheduler error")
                await asyncio.sleep(self.check_interval)

    async def stop_scheduler(self) -> None:
        """Stop the scheduler gracefully"""
        self.running = False
        logger.info("Task scheduler stopped")

    async def _check_scheduled_jobs(
        self,
        enqueue_callback: Callable[[JobProtocol], Any],
    ) -> None:
        """Check for jobs that are due to run

        Args:
            enqueue_callback: Function to enqueue jobs
        """
        current_time = time.time()

        for job_id, scheduled_job in list(self.scheduled_jobs.items()):
            if not scheduled_job.enabled:
                continue

            if current_time >= scheduled_job.next_run:
                # JobProtocol is due, create and enqueue it
                job = scheduled_job.job_template.create_job()
                try:
                    await enqueue_callback(job)
                    logger.info("Enqueued scheduled job %s: %s", job_id, job.name)

                    # Calculate next run time and persist it.
                    scheduled_job.next_run = scheduled_job.calculate_next_run()
                    if self._store:
                        try:
                            await self._store.update_next_run(
                                job_id, scheduled_job.next_run
                            )
                        except Exception:  # noqa: BLE001 — best-effort
                            logger.exception(
                                "Failed to persist next_run for job %s", job_id
                            )

                except Exception:  # noqa: BLE001 — handler isolation
                    # Intentionally broad: one job failing to enqueue should not stop the scheduler.
                    logger.exception("Failed to enqueue scheduled job %s", job_id)

    def enable_job(self, job_id: str) -> bool:
        """Enable a scheduled job

        Args:
            job_id: JobProtocol ID

        Returns:
            True if job was enabled
        """
        job = self.scheduled_jobs.get(job_id)
        if job:
            job.enabled = True
            logger.info("Enabled scheduled job %s", job_id)
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """Disable a scheduled job

        Args:
            job_id: JobProtocol ID

        Returns:
            True if job was disabled
        """
        job = self.scheduled_jobs.get(job_id)
        if job:
            job.enabled = False
            logger.info("Disabled scheduled job %s", job_id)
            return True
        return False

    def get_next_run_times(self) -> dict[str, float]:
        """Get next run times for all enabled scheduled jobs

        Returns:
            Dictionary mapping job ID to next run timestamp
        """
        return {
            job_id: scheduled_job.next_run
            for job_id, scheduled_job in self.scheduled_jobs.items()
            if scheduled_job.enabled
        }
