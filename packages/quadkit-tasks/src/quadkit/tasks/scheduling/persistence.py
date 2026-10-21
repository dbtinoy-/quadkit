"""Durable scheduler state persistence for :class:`~quadkit.tasks.scheduling.scheduler.TaskScheduler`.

Provides the :class:`SchedulerStore` protocol and two backends:

* :class:`InMemorySchedulerStore` — non-durable, wraps the scheduler's dict (testing).
* :class:`DatabaseSchedulerStore` — persists job definitions and next-run times to a
  relational database via :class:`~quadkit.contracts.data.DatabaseProviderProtocol`.

The ``DatabaseSchedulerStore`` is safe to use across multiple instances, but
it does not provide cross-process leader election: ``LockManager`` is
process-local only. In multi-instance deployments, use a distributed lock
(e.g. from ``the optional provider``) to elect the single instance that drives
the scheduler loop.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from quadkit.contracts.data.sql.database import provider_dialect
from quadkit.logging import get_logger
import quadkit.serialization as json
from quadkit.tasks.dialect import translate_placeholders
from quadkit.tasks.scheduling.templates import JobTemplateProtocol

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol
    from quadkit.tasks.scheduling.scheduler import ScheduledJob

logger = get_logger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    job_id          TEXT      NOT NULL PRIMARY KEY,
    cron_expression TEXT      NOT NULL,
    next_run        REAL      NOT NULL,
    enabled         INTEGER   NOT NULL DEFAULT 1,
    template_json   TEXT      NOT NULL,
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL
)
"""

_UPSERT_SQL = (
    "INSERT INTO scheduled_jobs "
    "(job_id, cron_expression, next_run, enabled, template_json, created_at, updated_at) "
    "VALUES (?, ?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (job_id) DO UPDATE SET "
    "cron_expression = excluded.cron_expression, "
    "next_run = excluded.next_run, "
    "enabled = excluded.enabled, "
    "template_json = excluded.template_json, "
    "updated_at = excluded.updated_at"
)

_GET_ALL_SQL = (
    "SELECT job_id, cron_expression, next_run, enabled, template_json "
    "FROM scheduled_jobs"
)

_UPDATE_NEXT_RUN_SQL = (
    "UPDATE scheduled_jobs SET next_run = ?, updated_at = ? WHERE job_id = ?"
)

_DELETE_SQL = "DELETE FROM scheduled_jobs WHERE job_id = ?"

__all__ = [
    "DatabaseSchedulerStore",
    "InMemorySchedulerStore",
    "SchedulerStore",
]


@runtime_checkable
class SchedulerStore(Protocol):
    """Protocol for persisting :class:`~quadkit.tasks.scheduling.scheduler.ScheduledJob` definitions.

    Implementations must support save, load, update, and delete operations.
    All methods are async.
    """

    async def save_job(self, job_id: str, job: ScheduledJob) -> None:
        """Persist (or overwrite) a scheduled job definition.

        Args:
            job_id: Unique identifier for this scheduled job.
            job: The ScheduledJob instance to persist.
        """
        ...

    async def load_jobs(self) -> dict[str, ScheduledJob]:
        """Load all persisted job definitions.

        Returns:
            Mapping of job_id to ScheduledJob for all stored jobs.
        """
        ...

    async def update_next_run(self, job_id: str, next_run: float) -> None:
        """Update the next-run timestamp for a scheduled job.

        Called after each successful job execution to advance the schedule.

        Args:
            job_id: Unique identifier for the scheduled job.
            next_run: Unix timestamp of the next execution.
        """
        ...

    async def delete_job(self, job_id: str) -> None:
        """Remove a scheduled job from the store.

        Args:
            job_id: Unique identifier for the scheduled job to remove.
        """
        ...


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


class InMemorySchedulerStore:
    """Non-durable :class:`SchedulerStore` backed by an in-memory dict.

    Useful for testing.  State is lost when the process exits.
    """

    def __init__(self) -> None:
        """Create a new in-memory scheduler store."""
        self._jobs: dict[str, ScheduledJob] = {}

    async def save_job(self, job_id: str, job: ScheduledJob) -> None:
        """Store a scheduled job in memory.

        Args:
            job_id: Unique identifier for this scheduled job.
            job: The ScheduledJob to store.
        """
        self._jobs[job_id] = job

    async def load_jobs(self) -> dict[str, ScheduledJob]:
        """Return all stored jobs.

        Returns:
            Copy of the internal job mapping.
        """
        return dict(self._jobs)

    async def update_next_run(self, job_id: str, next_run: float) -> None:
        """Update the next-run timestamp in memory.

        Args:
            job_id: Unique identifier for the scheduled job.
            next_run: Unix timestamp of the next execution.
        """
        job = self._jobs.get(job_id)
        if job is not None:
            job.next_run = next_run

    async def delete_job(self, job_id: str) -> None:
        """Remove a job from memory.

        Args:
            job_id: Unique identifier for the scheduled job to remove.
        """
        self._jobs.pop(job_id, None)


def _template_to_json(template: JobTemplateProtocol) -> str:
    """Serialize a JobTemplateProtocol as a JSON string.

    Args:
        template: JobTemplateProtocol to serialize.

    Returns:
        JSON string representation.
    """
    data = asdict(template)
    # tuple → list is fine for JSON; reconstruct on load
    return json.dumps(data).decode()


def _template_from_json(template_json: str) -> JobTemplateProtocol:
    """Reconstruct a JobTemplateProtocol from a JSON string.

    Args:
        template_json: JSON string produced by :func:`_template_to_json`.

    Returns:
        Reconstructed JobTemplateProtocol.
    """
    data = json.loads(template_json)
    data["args"] = tuple(data.get("args", []))
    return JobTemplateProtocol(**data)


class DatabaseSchedulerStore:
    """Durable :class:`SchedulerStore` backed by a relational database.

    Persists scheduled job definitions (cron expression, template, next-run time)
    to a ``scheduled_jobs`` table created lazily on first access.

    Note:
        ``LockManager`` is process-local only: a lock held by one instance
        is invisible to other instances. Use it to guard the scheduler loop
        within a single process, and pair with a distributed lock (e.g. from
        ``the optional provider``) when multiple instances must elect a single
        leader::

            lock_mgr = LockManager()
            async with lock_mgr.acquire("scheduler:leader", timeout=120):
                await scheduler.start_scheduler(queue.enqueue)

    Args:
        db: Database provider resolved from the DI container.
    """

    def __init__(self, db: DatabaseProviderProtocol) -> None:
        """Create a database-backed scheduler store.

        Args:
            db: Database provider from the DI container.
        """
        self._db = db
        self._initialised = False

    def _sql(self, sql: str) -> str:
        """Translate ``?`` placeholders to the provider dialect style."""
        dialect = provider_dialect(self._db)
        return translate_placeholders(sql, dialect)

    async def _ensure_table(self) -> None:
        """Create the scheduled_jobs table if it does not yet exist."""
        if not self._initialised:
            await self._db.execute(self._sql(_CREATE_TABLE_SQL))
            self._initialised = True

    async def save_job(self, job_id: str, job: ScheduledJob) -> None:
        """Upsert a scheduled job definition to the database.

        Args:
            job_id: Unique identifier for this scheduled job.
            job: The ScheduledJob to persist.
        """
        await self._ensure_table()
        now = datetime.now(UTC)
        template_json = _template_to_json(job.job_template)
        await self._db.execute(
            self._sql(_UPSERT_SQL),
            [
                job_id,
                job.cron_expression,
                job.next_run,
                int(job.enabled),
                template_json,
                now,
                now,
            ],
        )
        logger.debug("scheduler.job_saved", job_id=job_id)

    async def load_jobs(self) -> dict[str, ScheduledJob]:
        """Load all scheduled jobs from the database.

        Returns:
            Mapping of job_id to ScheduledJob for all persisted jobs.
        """
        await self._ensure_table()
        # Import here to avoid a circular import at module level.
        from quadkit.tasks.scheduling.scheduler import ScheduledJob

        query_result = await self._db.execute_query(self._sql(_GET_ALL_SQL))
        jobs: dict[str, ScheduledJob] = {}
        for row in query_result.rows:
            template = _template_from_json(row["template_json"])
            jobs[row["job_id"]] = ScheduledJob(
                job_template=template,
                cron_expression=row["cron_expression"],
                next_run=float(row["next_run"]),
                enabled=bool(row["enabled"]),
            )
        logger.debug("scheduler.jobs_loaded", count=len(jobs))
        return jobs

    async def update_next_run(self, job_id: str, next_run: float) -> None:
        """Update the next-run timestamp for a scheduled job in the database.

        Args:
            job_id: Unique identifier for the scheduled job.
            next_run: Unix timestamp of the next execution.
        """
        await self._ensure_table()
        await self._db.execute(
            self._sql(_UPDATE_NEXT_RUN_SQL),
            [next_run, datetime.now(UTC), job_id],
        )
        logger.debug("scheduler.next_run_updated", job_id=job_id, next_run=next_run)

    async def delete_job(self, job_id: str) -> None:
        """Remove a scheduled job from the database.

        Args:
            job_id: Unique identifier for the scheduled job to remove.
        """
        await self._ensure_table()
        await self._db.execute(self._sql(_DELETE_SQL), [job_id])
        logger.debug("scheduler.job_deleted", job_id=job_id)
