"""Migration scheduling functionality."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from quadkit.contracts.core import TaskManagerProtocol
from quadkit.events.schema.migration.migrator import SchemaMigrator
from quadkit.events.schema.migration.types import MigrationResult
from quadkit.logging import get_logger

logger = get_logger(__name__)


class MigrationScheduler:
    """Schedule and manage schema migrations.

    This class provides scheduling capabilities for running
    migrations at specific times or intervals.

    Example:
        ```python
        scheduler = MigrationScheduler(migrator)

        # Schedule migration
        job_id = await scheduler.schedule_migration(
            version_map={"UserCreated": 3},
            run_at=datetime.now() + timedelta(hours=1),
        )

        # Check status
        status = await scheduler.get_job_status(job_id)
        ```
    """

    def __init__(
        self,
        migrator: SchemaMigrator,
        task_manager: TaskManagerProtocol,
    ) -> None:
        """Initialize migration scheduler.

        Args:
            migrator: Schema migrator instance.
            task_manager: Task manager for background tasks.
        """
        self.migrator = migrator
        self._task_manager = task_manager
        self._jobs: dict[str, dict[str, Any]] = {}
        self._results: dict[str, MigrationResult] = {}

    async def schedule_migration(
        self,
        version_map: dict[str, int],
        run_at: datetime | None = None,
        callback: Callable[[MigrationResult], None] | None = None,
    ) -> str:
        """Schedule a migration.

        Args:
            version_map: Event type to version mapping.
            run_at: When to run (None for immediate).
            callback: Optional callback on completion.

        Returns:
            JobProtocol ID.
        """
        job_id = str(uuid4())

        self._jobs[job_id] = {
            "id": job_id,
            "version_map": version_map,
            "run_at": run_at,
            "callback": callback,
            "status": "scheduled",
        }

        if run_at is None:
            # Run immediately
            self._task_manager.create_background_task(
                self._run_migration(job_id),
                name=f"migration_job_{job_id}",
            )
        else:
            # Schedule for later.  Naive run_at values are assumed to be
            # UTC (the package convention) so the documented
            # ``datetime.now() + timedelta(...)`` usage does not raise
            # on the naive-vs-aware subtraction.
            if run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=UTC)
            delay = (run_at - datetime.now(UTC)).total_seconds()
            if delay > 0:
                self._task_manager.create_background_task(
                    self._delayed_migration(job_id, delay),
                    name=f"delayed_migration_{job_id}",
                )
            else:
                self._task_manager.create_background_task(
                    self._run_migration(job_id),
                    name=f"migration_job_{job_id}",
                )

        return job_id

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get the status of a migration job.

        Args:
            job_id: JobProtocol identifier.

        Returns:
            JobProtocol status or None if not found.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None

        status = dict(job)
        if job_id in self._results:
            status["result"] = self._results[job_id]

        return status

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a scheduled migration.

        Args:
            job_id: JobProtocol identifier.

        Returns:
            True if cancelled, False if not found or already running.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return False

        if job["status"] == "running":
            self.migrator.cancel()
            return True

        if job["status"] == "scheduled":
            job["status"] = "cancelled"
            return True

        return False

    async def _run_migration(self, job_id: str) -> None:
        """Run a migration job."""
        job = self._jobs.get(job_id)
        if job is None:
            return

        job["status"] = "running"

        try:
            result = await self.migrator.migrate_all_events(job["version_map"])
            self._results[job_id] = result
            job["status"] = "completed"

            if job["callback"]:
                job["callback"](result)

        except Exception as e:  # noqa: BLE001 — migration job catch-all; marks job failed without crashing scheduler
            job["status"] = "failed"
            job["error"] = str(e)
            logger.exception("Migration job %s failed", job_id)

    async def _delayed_migration(self, job_id: str, delay: float) -> None:
        """Run a delayed migration."""
        await asyncio.sleep(delay)
        await self._run_migration(job_id)


__all__ = ["MigrationScheduler"]
