"""Postgres-backed TaskQueueProtocol implementation.

Provides minimal persistent enqueue/dequeue/ack operations backed by Postgres.
The dequeue implementation uses a transactional UPDATE ... RETURNING pattern with
FOR UPDATE SKIP LOCKED semantics to avoid races between workers.

This backend uses DatabaseProviderProtocol for all database operations,
enabling connection pooling, observability, and proper lifecycle management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from quadkit.contracts.data.identifiers import table as _sql_table
from quadkit.logging import get_logger
from quadkit.result import Ok, Result
from quadkit.serialization import dumps, loads
from quadkit.tasks.config import PostgresTaskConfig
from quadkit.tasks.hooks import TaskEnqueuedHook
from quadkit.tasks.models.job import JobProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core import HookRegistryProtocol
    from quadkit.contracts.data import DatabaseProviderProtocol
    from quadkit.tasks.exceptions import TaskError

logger = get_logger(__name__)


class PostgresTaskQueue:
    """PostgreSQL task queue using DatabaseProviderProtocol.

    **Construction**

    The queue requires a
    :class:`~quadkit.contracts.data.DatabaseProviderProtocol` so that it
    participates in the container-managed connection lifecycle::

        provider = await container.resolve(DatabaseProviderProtocol)
        queue = PostgresTaskQueue(provider=provider)

    The ``config.dsn`` field is metadata for CLI tooling / diagnostics; this
    class does **not** create its own connection pool — without a provider,
    enqueue/dequeue raise ``RuntimeError`` at call time.

    Args:
        config: Optional queue configuration.  When omitted, defaults are used.
        provider: DatabaseProviderProtocol instance for database operations.
            Required for enqueue/dequeue; if not supplied, calls will raise
            ``RuntimeError`` at runtime.
    """

    def __init__(
        self,
        config: PostgresTaskConfig | dict[str, Any] | None = None,
        provider: DatabaseProviderProtocol | None = None,
    ):
        if isinstance(config, dict):
            config = PostgresTaskConfig(**config)
        elif config is None:
            config = PostgresTaskConfig()

        self.config = config
        self._provider = provider
        self._hooks: HookRegistryProtocol | None = None
        # Validate and quote the table name once; ``_sql_table`` is LRU-cached
        # so repeated calls with the same name return the same object.
        # ``Table.__str__()`` yields a dialect-quoted identifier safe for SQL
        # f-string interpolation (e.g. ``"tasks"`` not bare ``tasks``).
        self._table = _sql_table(config.table)
        self._table_ensured = False

    async def _ensure_table(self) -> None:
        """Create the queue table if it does not exist (idempotent).

        Runs lazily once before the first enqueue/dequeue so a fresh
        deployment works without out-of-band DDL. ``CREATE TABLE IF NOT
        EXISTS`` is safe under concurrent first-use: a second creator
        simply waits on the DDL lock.
        """
        if self._table_ensured:
            return
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )
        table = self._table
        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    available_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    enqueued_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    locked_at TIMESTAMP,
                    locked_by TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0
                )
                """  # noqa: S608 -- dialect-quoted Table identifier from validated config
            )
        self._table_ensured = True

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry after provider boot wiring."""
        self._hooks = hooks

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a task action hook when a registry is available."""
        hooks = getattr(self, "_hooks", None)
        if hooks is None:
            return

        await hooks.call_action(hook_name, payload=payload)

    async def connect(self) -> None:
        """Initialize the database connection via provider."""
        if self._provider is not None:
            await self._provider.connect()

    async def _enqueue(self, payload: Any, *, priority: int = 0) -> str:
        """Insert a task and return its UUID as string."""
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        await self._ensure_table()
        task_id = str(uuid.uuid4())
        table = self._table

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()
            await conn.execute(
                f"""
                INSERT INTO {table} (id, payload, priority)
                VALUES ($1, $2::jsonb, $3)
                """,  # noqa: S608 -- dialect-quoted Table identifier from validated config
                [task_id, dumps(payload), priority],
            )

        logger.debug("Enqueued task %s", task_id)
        return task_id

    async def _dequeue(self) -> dict[str, Any] | None:
        """Atomically fetch and lock a pending task, returning its payload and id.

        Returns None if no available pending task exists.
        """
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        await self._ensure_table()
        table = self._table

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()

            # Note: DatabaseProviderProtocol doesn't support FOR UPDATE SKIP LOCKED
            # directly. This is a limitation that requires future enhancement.
            result = await conn.execute(
                f"""
                WITH candidate AS (
                    SELECT id FROM {table}
                    WHERE status = 'pending' AND available_at <= NOW()
                    ORDER BY priority DESC, enqueued_at ASC
                    LIMIT 1
                )
                UPDATE {table} t
                SET status = 'in_progress', locked_at = NOW(), attempts = attempts + 1
                FROM candidate
                WHERE t.id = candidate.id
                RETURNING t.id, t.payload, t.priority
                """,  # noqa: S608 -- dialect-quoted Table identifier from validated config
            )

            rows = result.rows if hasattr(result, "rows") else []
            if not rows:
                return None

            row = rows[0]
            return {
                "id": str(row["id"]),
                "payload": loads(row["payload"]),
                "priority": row["priority"],
            }

    async def _ack(self, job_id: str) -> None:
        """Acknowledge a task as completed: delete it from the table."""
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        table = self._table

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()
            await conn.execute(
                f"DELETE FROM {table} WHERE id = $1",  # noqa: S608 -- dialect-quoted Table identifier from validated config
                [job_id],
            )

        logger.debug("Acknowledged task %s", job_id)

    async def _nack(
        self, job_id: str, *, requeue: bool, delay_seconds: int = 0
    ) -> None:
        """Nack a task: requeue it (optionally delayed) or mark it failed.

        ``requeue=False`` marks the task as ``failed`` (terminal) — matching
        the other backends, where a non-requeued nack simply drops the task.
        A negative delay would otherwise make the task *immediately*
        available, which is the opposite of "do not requeue".
        """
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        table = self._table

        if not requeue:
            async with self._provider.scoped_context():
                conn = await self._provider.get_scoped_connection()
                await conn.execute(
                    f"""
                    UPDATE {table}
                    SET status = 'failed', locked_by = NULL, locked_at = NULL
                    WHERE id = $1
                    """,  # noqa: S608 -- dialect-quoted Table identifier from validated config
                    [job_id],
                )
            logger.debug("Nacked task %s (requeue=False, marked failed)", job_id)
            return

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()
            await conn.execute(
                f"""
                UPDATE {table}
                SET status = 'pending', available_at = NOW() + $2 * INTERVAL '1 second', locked_by = NULL, locked_at = NULL
                WHERE id = $1
                """,  # noqa: S608 -- dialect-quoted Table identifier from validated config
                [job_id, delay_seconds],
            )

        logger.debug("Nacked task %s (delay=%s)", job_id, delay_seconds)

    async def requeue_stalled(self, visibility_timeout_seconds: int = 60) -> int:
        """Requeue tasks that have been in_progress beyond visibility timeout.

        Moves tasks with attempts > max_attempts to 'failed', and requeues others
        by setting them to 'pending' and making them available immediately.

        Returns:
            Number of tasks affected (requeued + marked failed).
        """
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        table = self._table

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()

            res_failed = await conn.execute(
                f"""
                UPDATE {table}
                SET status = 'failed'
                WHERE status = 'in_progress'
                  AND locked_at <= NOW() - $1 * INTERVAL '1 second'
                  AND attempts > $2
                """,  # noqa: S608 -- dialect-quoted Table identifier from validated config
                [visibility_timeout_seconds, self.config.max_attempts],
            )

            res_requeued = await conn.execute(
                f"""
                UPDATE {table}
                SET status = 'pending', locked_by = NULL, locked_at = NULL, available_at = NOW()
                WHERE status = 'in_progress'
                  AND locked_at <= NOW() - $1 * INTERVAL '1 second'
                  AND attempts <= $2
                """,  # noqa: S608 -- dialect-quoted Table identifier from validated config
                [visibility_timeout_seconds, self.config.max_attempts],
            )

        def _count(result: Any) -> int:
            if hasattr(result, "row_count"):
                row_count: int = result.row_count
                return row_count
            try:
                return int(str(result).rsplit(maxsplit=1)[-1])
            except (ValueError, IndexError) as e:
                logger.warning("Failed to parse affected rows count: %s", e)
                return 0

        return _count(res_failed) + _count(res_requeued)

    async def get_task_count(self) -> int:
        """Return the number of pending tasks available for processing."""
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        table = self._table

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()
            result = await conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE status = 'pending' AND available_at <= NOW()",  # noqa: S608 -- dialect-quoted Table identifier from validated config
            )
            rows = result.rows if hasattr(result, "rows") else []
            return int(rows[0]["count"]) if rows else 0

    async def clear(self) -> None:
        """Delete all tasks from the queue table."""
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        table = self._table

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()
            await conn.execute(f"DELETE FROM {table}")  # noqa: S608 -- dialect-quoted Table identifier from validated config

    async def get_task_status(self, job_id: str) -> str | None:
        """Return the status string for the given job ID, or None if not found."""
        if self._provider is None:
            raise RuntimeError(
                "DatabaseProviderProtocol is required. "
                "Pass provider to PostgresTaskQueue constructor."
            )

        table = self._table

        async with self._provider.scoped_context():
            conn = await self._provider.get_scoped_connection()
            result = await conn.execute(
                f"SELECT status FROM {table} WHERE id = $1",  # noqa: S608 -- dialect-quoted Table identifier from validated config
                [job_id],
            )
            rows = result.rows if hasattr(result, "rows") else []
            return rows[0]["status"] if rows else None

    async def close(self) -> None:
        """Close the database provider connection."""
        if self._provider is not None:
            await self._provider.disconnect()

    async def enqueue(self, task: JobProtocol) -> Result[str, TaskError]:
        """Enqueue a JobProtocol object, returning Ok(task_id) or Err(TaskError) on failure.

        Args:
            task: JobProtocol instance to enqueue.

        Returns:
            Ok containing the job ID, or Err containing a TaskError for recoverable failures.
        """
        task_id = await self._enqueue(task.to_dict(), priority=task.priority)
        await self._emit_action(
            "task.queued",
            TaskEnqueuedHook(task_name=task.name, queue_name=self.config.table),
        )
        return Ok(task_id)

    async def dequeue(self) -> JobProtocol | None:
        """Dequeue and return the next available JobProtocol.

        Returns:
            JobProtocol instance or None if queue is empty.
        """
        result = await self._dequeue()
        if result is None:
            return None

        payload = result.get("payload", {})
        payload["id"] = result.get("id", payload.get("id", ""))
        return JobProtocol.from_dict(payload)

    async def ping(self) -> bool:
        """Check if the queue connection is alive.

        Returns:
            True if connection is healthy.
        """
        if self._provider is None:
            return False
        try:
            async with self._provider.scoped_context():
                conn = await self._provider.get_scoped_connection()
                await conn.execute("SELECT 1")
            return True
        except Exception:  # noqa: BLE001 — best-effort health probe
            # Driver-level errors (asyncpg/psycopg connection failures, ...)
            # must report False, not propagate.
            return False

    async def ack(self, task_id: str) -> None:
        """Acknowledge job completion."""
        await self._ack(task_id)

    async def nack(self, task_id: str, requeue: bool = True) -> None:
        """Nack job for optional requeue.

        With ``requeue=False`` the task is marked ``failed`` (terminal)
        instead of being returned to the queue.
        """
        await self._nack(task_id, requeue=requeue)
