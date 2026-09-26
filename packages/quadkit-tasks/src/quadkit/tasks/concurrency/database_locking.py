"""Database-backed locking for cross-process task exclusion.

``LockManager`` and ``distributed_lock`` in :mod:`quadkit.tasks.concurrency.locking`
are process-local: a lock held by one instance is invisible to every other
instance, which the scheduler store documents as a limitation and asks callers
to work around with an external distributed lock. This module is that lock,
without a new dependency — it uses the database the application already has.

Design:
- One row per lock key. The row is the lock.
- ``acquire`` is a single ``INSERT ... ON CONFLICT DO UPDATE ... WHERE``
  statement, so the winner is decided by the database in one round trip
  (no read-then-write race between two instances).
- Locks expire (``locked_until``), so a process that dies while holding one
  releases it by timing out instead of blocking the key forever. A holder may
  :meth:`DatabaseLockHandle.renew` to extend a long operation.
- Ownership is verified after every write: a statement that *intended* to claim
  a key never reports success on a key another holder owns.

Portability: only ``?`` placeholders are translated (via
:func:`quadkit.tasks.dialect.translate_placeholders`), and the statements use
constructs shared by SQLite and PostgreSQL. Table and column names are
configurable — an application that already has a lock table (for example from a
migration) points the manager at it instead of growing a second one.

Example:
    ```python
    manager = DatabaseLockManager(db, table="system_task_locks", key_column="type")
    async with manager.hold("log_cleanup", holder=instance_id, ttl_seconds=120) as lock:
        for batch in batches:
            await process(batch)
            await lock.renew()
    ```
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
import re
import socket
import time
from typing import Any, Protocol, Self
import uuid

from quadkit.logging import get_logger
from quadkit.tasks.dialect import translate_placeholders
from quadkit.tasks.exceptions import TaskLockHeldError

logger = get_logger(__name__)

__all__ = [
    "DatabaseLockHandle",
    "DatabaseLockManager",
    "LockSnapshot",
    "SqlExecutor",
    "default_holder_id",
]

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(name: str, *, role: str) -> str:
    """Validate a SQL identifier before it is interpolated into a statement.

    Table and column names cannot be bound as parameters, so they are
    interpolated; validating them keeps a configuration mistake from becoming
    an injection point.

    Args:
        name: Candidate identifier.
        role: What the identifier is (for the error message).

    Returns:
        The identifier, unchanged.

    Raises:
        ValueError: The name is not a plain SQL identifier.
    """
    if not _IDENTIFIER.match(name):
        raise ValueError(f"{role} must be a plain SQL identifier, got {name!r}")
    return name


def default_holder_id() -> str:
    """Return a stable-ish identity for the current process.

    Holder ids only need to be unique among the instances sharing a database —
    they are compared for ownership, never trusted for authorization — so
    hostname plus a random suffix is enough.

    Returns:
        A ``host:pid:random`` style identifier.
    """
    import os

    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


@dataclass(frozen=True)
class LockSnapshot:
    """State of one lock key at a point in time.

    Attributes:
        key: The lock key.
        holder: Who holds it, or ``None`` when the row does not exist.
        expires_at: Epoch seconds at which the current hold lapses.
        held: Whether the key is held right now (row exists and has not expired).
        now: The clock reading the snapshot was taken at. Kept with the
            snapshot so the remaining TTL is derived from the same time source
            that set the expiry (the manager's clock, which tests may move).
    """

    key: str
    holder: str | None
    expires_at: float | None
    held: bool
    now: float = 0.0

    @property
    def ttl_remaining(self) -> float:
        """Seconds left before the hold lapses (``0.0`` when not held)."""
        if not self.held or self.expires_at is None:
            return 0.0
        return max(0.0, self.expires_at - self.now)


class SqlExecutor(Protocol):
    """Marker for the database providers this module accepts.

    Providers differ in how they run a statement with parameters, so the
    manager does not call one named method: it picks the first surface the
    provider offers, in this order,

    1. ``session()`` — an async context manager yielding a connection with
       ``exec_driver_sql(sql, params)`` (SQLAlchemy-style providers, including
       this workspace's ``DatabaseProvider``);
    2. ``execute_modify(sql, params)`` / ``execute_query(sql, params)``
       (``quadkit-sql`` providers);
    3. ``execute(sql, params)`` — a duck-typed fallback for a provider that
       exposes a single raw-statement entry point.

    A provider with none of them raises :class:`TypeError` at the first
    statement, which is a louder failure than silently locking nothing.
    """


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Normalise a result row to a dict.

    Providers hand back SQLAlchemy ``Row`` objects (``._mapping``), mappings, or
    plain dicts; the lock statements are the same either way, so the runner
    accepts all three rather than forcing a provider to change shape.

    Args:
        row: A row as returned by the provider.

    Returns:
        The row as a dict.
    """
    mapping = getattr(row, "_mapping", None)
    if mapping is not None:
        return dict(mapping)
    return dict(row)


class _StatementRunner:
    """Runs statements through whichever surface the provider exposes."""

    def __init__(self, db: SqlExecutor) -> None:
        self._db: Any = db
        if callable(getattr(db, "session", None)):
            self._surface = "session"
        elif callable(getattr(db, "execute_modify", None)):
            self._surface = "quadkit_sql"
        elif callable(getattr(db, "execute", None)):
            self._surface = "execute"
        else:
            raise TypeError(
                "DatabaseLockManager needs a database provider with session(), "
                "execute_modify()/execute_query(), or execute(); got "
                f"{type(db).__name__}"
            )

    @property
    def surface(self) -> str:
        """Which provider surface is in use (for diagnostics and logging)."""
        return self._surface

    async def dialect(self) -> str:
        """Best-effort dialect name for placeholder translation.

        Tries the provider's ``name`` first (the convention used elsewhere in
        this package), then the driver's dialect through ``engine`` /
        ``connection``, and falls back to SQLite — whose ``?`` style is what
        the statements are written in, so an unknown dialect degrades to the
        authoring style rather than corrupting it.

        Returns:
            A dialect name such as ``"sqlite"`` or ``"postgres"``.
        """
        name = getattr(self._db, "name", None)
        if isinstance(name, str) and name:
            return name

        engine = getattr(self._db, "engine", None)
        sync_engine = getattr(engine, "sync_engine", engine)
        dialect = getattr(getattr(sync_engine, "dialect", None), "name", None)
        if isinstance(dialect, str) and dialect:
            return dialect

        connection = getattr(self._db, "connection", None)
        dialect = getattr(getattr(connection, "dialect", None), "name", None)
        if isinstance(dialect, str) and dialect:
            return dialect
        return "sqlite"

    async def run(self, sql: str, params: list[Any]) -> list[dict[str, Any]] | int:
        """Execute one statement and return rows, or an affected-row count.

        Args:
            sql: Statement with ``?`` placeholders.
            params: Bind parameters in placeholder order.

        Returns:
            Rows as dicts for a SELECT, otherwise the affected row count
            (``0`` when the provider does not report one).
        """
        translated = translate_placeholders(sql, await self.dialect())
        # Which field of a result object carries the answer follows from the
        # statement, not from the provider: a read returns rows, a write
        # returns an affected-row count, and some providers fill both fields
        # for every call.
        reading = translated.lstrip().upper().startswith("SELECT")

        if self._surface == "session":
            async with self._db.session() as session:
                # SQLAlchemy sessions need .connection() first; a provider that
                # already yields a connection is used as-is.
                connection = getattr(session, "connection", None)
                conn = await connection() if callable(connection) else session
                result = await conn.exec_driver_sql(translated, tuple(params))
                if reading:
                    return [_row_to_dict(row) for row in result]
                return int(result.rowcount or 0)

        if self._surface == "quadkit_sql":
            if reading:
                result = await self._db.execute_query(translated, params)
                rows = getattr(result, "rows", None)
                return [_row_to_dict(row) for row in rows] if rows else []
            result = await self._db.execute_modify(translated, params)
            affected = getattr(result, "affected_rows", None)
            if affected is None:
                affected = getattr(result, "influenced_rows", None)
            return int(affected or 0)

        result = await self._db.execute(translated, params)
        if reading:
            rows = getattr(result, "rows", None)
            if rows is None and isinstance(result, list):
                rows = result
            return [_row_to_dict(row) for row in rows] if rows else []
        affected = getattr(result, "affected_rows", None)
        if affected is None:
            affected = getattr(result, "rowcount", None)
        if affected is not None:
            return int(affected)
        return int(result) if isinstance(result, int) else 0


class DatabaseLockHandle:
    """A held database lock.

    Obtained from :meth:`DatabaseLockManager.hold` or
    :meth:`DatabaseLockManager.acquire`. Renewing keeps a long operation from
    expiring out from under its owner; releasing is what makes the key
    available to the next caller instead of waiting for the TTL.
    """

    def __init__(
        self, manager: DatabaseLockManager, key: str, holder: str, ttl_seconds: float
    ) -> None:
        """Create a handle (use the manager's methods, not this constructor).

        Args:
            manager: The manager that granted the lock.
            key: The lock key.
            holder: The holder id that owns it.
            ttl_seconds: How long each acquisition/renewal lasts.
        """
        self._manager = manager
        self.key = key
        self.holder = holder
        self.ttl_seconds = ttl_seconds
        self._released = False

    async def renew(self, ttl_seconds: float | None = None) -> bool:
        """Extend the hold, if this handle still owns the key.

        Args:
            ttl_seconds: New lifetime in seconds (defaults to the original).

        Returns:
            ``True`` when the hold was extended. ``False`` means the lock was
            lost (expired and taken over, or released); callers should stop
            work that requires exclusivity rather than retry blindly.
        """
        if self._released:
            return False
        return await self._manager.renew(
            self.key, self.holder, ttl_seconds or self.ttl_seconds
        )

    async def release(self) -> bool:
        """Release the key if this handle owns it.

        Returns:
            ``True`` when this handle removed its own row.
        """
        self._released = True
        return await self._manager.release(self.key, self.holder)

    async def __aenter__(self) -> Self:
        """Enter the context with the lock already held.

        Returns:
            This handle.
        """
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Release the key when the context exits.

        Args:
            *exc_info: Exception details, unused — the lock is released whether
                the block succeeded or failed.
        """
        await self.release()


class DatabaseLockManager:
    """Exclusive, expiring locks over a database table.

    Args:
        db: Database provider (see :class:`SqlExecutor` for the accepted
            surfaces).
        table: Lock table name.
        key_column: Column holding the lock key (primary key).
        holder_column: Column holding the current holder id.
        until_column: Column holding the expiry, in epoch seconds.
        updated_column: Column holding the last write time, in epoch seconds.
        extra_columns: Additional columns written on acquisition (for example a
            ``task_id`` column that an existing table requires). Values are
            passed to :meth:`acquire` as keyword arguments.
        clock: Time source, injectable for tests.
        ensure_table: Create the table when missing. Applications that own the
            schema through migrations may pass ``False`` to keep start-up
            read-only.

    Raises:
        ValueError: A table or column name is not a plain SQL identifier.
        TypeError: The provider exposes none of the supported surfaces.
    """

    def __init__(
        self,
        db: SqlExecutor,
        *,
        table: str = "quadkit_task_locks",
        key_column: str = "lock_key",
        holder_column: str = "locked_by",
        until_column: str = "locked_until",
        updated_column: str = "updated_at",
        extra_columns: Iterable[str] = (),
        clock: Callable[[], float] = time.time,
        ensure_table: bool = True,
    ) -> None:
        self._table = _identifier(table, role="table")
        self._key_column = _identifier(key_column, role="key_column")
        self._holder_column = _identifier(holder_column, role="holder_column")
        self._until_column = _identifier(until_column, role="until_column")
        self._updated_column = _identifier(updated_column, role="updated_column")
        self._extra_columns = tuple(
            _identifier(c, role="extra_columns") for c in extra_columns
        )
        self._clock = clock
        self._ensure_table = ensure_table
        self._runner = _StatementRunner(db)
        self._table_ready = False

    @property
    def table(self) -> str:
        """The lock table this manager writes to."""
        return self._table

    @property
    def surface(self) -> str:
        """Which provider surface statements are executed through."""
        return self._runner.surface

    def _qualified(self) -> str:
        return self._table

    async def ensure_table(self) -> None:
        """Create the lock table when it does not exist.

        The DDL is deliberately minimal and portable — a text primary key and
        integer (epoch second) timestamps — so the same statement works on
        SQLite and PostgreSQL. Applications with their own lock table (created
        by a migration) never reach this path if they pass ``ensure_table=False``
        or already have the table.
        """
        if self._table_ready or not self._ensure_table:
            return
        columns = ",\n    ".join(
            [
                f"{self._key_column} TEXT NOT NULL PRIMARY KEY",
                f"{self._holder_column} TEXT NOT NULL",
                f"{self._until_column} BIGINT NOT NULL",
                f"{self._updated_column} BIGINT NOT NULL",
                *[f"{column} TEXT" for column in self._extra_columns],
            ]
        )
        await self._runner.run(
            f"CREATE TABLE IF NOT EXISTS {self._qualified()} (\n    {columns}\n)", []
        )
        self._table_ready = True

    async def acquire(
        self,
        key: str,
        holder: str,
        ttl_seconds: float = 60.0,
        **extra: Any,
    ) -> bool:
        """Claim a key for ``holder``, taking it over if the previous hold expired.

        Args:
            key: The lock key.
            holder: Holder id (see :func:`default_holder_id`).
            ttl_seconds: How long the claim lasts without renewal.
            **extra: Values for the configured ``extra_columns``.

        Returns:
            ``True`` when ``holder`` owns the key after the call.

        Raises:
            ValueError: An unknown extra column was passed, or the TTL is not
                positive.
        """
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        unknown = set(extra) - set(self._extra_columns)
        if unknown:
            raise ValueError(
                f"unknown lock columns {sorted(unknown)}; declare them in extra_columns"
            )
        missing = [column for column in self._extra_columns if column not in extra]
        if missing:
            # The table declares these columns, often NOT NULL: writing the row
            # without them would fail inside the database instead.
            raise ValueError(f"extra columns {missing} must be provided on acquire()")

        await self.ensure_table()
        now = self._clock()
        until = now + ttl_seconds

        columns = [
            self._key_column,
            self._holder_column,
            self._until_column,
            self._updated_column,
            *self._extra_columns,
        ]
        placeholders = ", ".join("?" for _ in columns)
        assignments = ", ".join(
            [f"{self._holder_column} = excluded.{self._holder_column}"]
            + [f"{column} = excluded.{column}" for column in self._extra_columns]
            + [
                f"{self._until_column} = excluded.{self._until_column}",
                f"{self._updated_column} = excluded.{self._updated_column}",
            ]
        )
        values: list[Any] = [
            key,
            holder,
            until,
            now,
            *[extra[column] for column in self._extra_columns],
        ]
        # The WHERE clause is what makes this a takeover-or-nothing statement:
        # a live hold by somebody else is left untouched.
        sql = (
            f"INSERT INTO {self._qualified()} ({', '.join(columns)})\n"
            f"VALUES ({placeholders})\n"
            f"ON CONFLICT ({self._key_column}) DO UPDATE SET {assignments}\n"
            f"WHERE {self._qualified()}.{self._until_column} <= ? "
            f"OR {self._qualified()}.{self._holder_column} = ?"
        )
        await self._runner.run(sql, [*values, now, holder])

        snapshot = await self.snapshot(key)
        return snapshot.held and snapshot.holder == holder

    async def renew(self, key: str, holder: str, ttl_seconds: float) -> bool:
        """Extend a hold owned by ``holder``.

        Args:
            key: The lock key.
            holder: The holder id that must still own the key.
            ttl_seconds: New lifetime in seconds.

        Returns:
            ``True`` when the row was updated (the caller still holds the key).
        """
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        await self.ensure_table()
        now = self._clock()
        affected = await self._runner.run(
            f"UPDATE {self._qualified()} SET {self._until_column} = ?, {self._updated_column} = ? "
            f"WHERE {self._key_column} = ? AND {self._holder_column} = ?",
            [now + ttl_seconds, now, key, holder],
        )
        return bool(affected)

    async def release(self, key: str, holder: str) -> bool:
        """Release a key owned by ``holder``.

        Args:
            key: The lock key.
            holder: The holder id; another holder's row is never deleted.

        Returns:
            ``True`` when a row was removed.
        """
        await self.ensure_table()
        affected = await self._runner.run(
            f"DELETE FROM {self._qualified()} WHERE {self._key_column} = ? AND {self._holder_column} = ?",
            [key, holder],
        )
        return bool(affected)

    async def snapshot(self, key: str) -> LockSnapshot:
        """Read the current state of a key.

        Args:
            key: The lock key.

        Returns:
            A :class:`LockSnapshot`; ``holder`` is ``None`` when the key is
            free (no row), and ``held`` is ``False`` for a row whose hold has
            expired.
        """
        await self.ensure_table()
        rows = await self._runner.run(
            f"SELECT {self._holder_column} AS holder, {self._until_column} AS expires_at "
            f"FROM {self._qualified()} WHERE {self._key_column} = ?",
            [key],
        )
        now = self._clock()
        if not isinstance(rows, list) or not rows:
            return LockSnapshot(
                key=key, holder=None, expires_at=None, held=False, now=now
            )

        holder = rows[0].get("holder")
        expires_at = rows[0].get("expires_at")
        expiry = float(expires_at) if expires_at is not None else 0.0
        held = holder is not None and expiry > now
        return LockSnapshot(
            key=key,
            holder=str(holder) if holder is not None else None,
            expires_at=expiry,
            held=held,
            now=now,
        )

    @asynccontextmanager
    async def hold(
        self,
        key: str,
        *,
        holder: str | None = None,
        ttl_seconds: float = 60.0,
        **extra: Any,
    ) -> AsyncGenerator[DatabaseLockHandle, None]:
        """Hold a key for the duration of a block, or fail loudly.

        Acquiring a lock this way never yields an unlocked section: when the
        key belongs to somebody else the call raises, mirroring
        :func:`quadkit.tasks.concurrency.locking.distributed_lock`.

        Args:
            key: The lock key.
            holder: Holder id (a process identity is generated when omitted).
            ttl_seconds: How long each claim lasts; call ``renew()`` on the
                handle for work that can outlive it.
            **extra: Values for the configured ``extra_columns``.

        Yields:
            The held :class:`DatabaseLockHandle`.

        Raises:
            TaskLockHeldError: The key is held by another holder.
        """
        owner = holder or default_holder_id()
        if not await self.acquire(key, owner, ttl_seconds, **extra):
            snapshot = await self.snapshot(key)
            raise TaskLockHeldError(
                f"Lock {key!r} is held by another instance",
                details={
                    "key": key,
                    "holder": snapshot.holder,
                    "ttl_remaining": round(snapshot.ttl_remaining, 3),
                },
                hint="Wait for the holder to finish (or for its lock to expire), then retry.",
            )

        handle = DatabaseLockHandle(self, key, owner, ttl_seconds)
        try:
            yield handle
        finally:
            await handle.release()

    async def acquire_or_wait(
        self,
        key: str,
        *,
        holder: str | None = None,
        ttl_seconds: float = 60.0,
        wait_seconds: float = 0.0,
        poll_interval: float = 0.5,
        **extra: Any,
    ) -> DatabaseLockHandle:
        """Acquire a key, optionally waiting for a holder to finish.

        Args:
            key: The lock key.
            holder: Holder id (a process identity is generated when omitted).
            ttl_seconds: How long each claim lasts.
            wait_seconds: How long to keep retrying before giving up
                (``0`` = single attempt).
            poll_interval: Delay between attempts.
            **extra: Values for the configured ``extra_columns``.

        Returns:
            The held handle, which the caller must ``release()``.

        Raises:
            TaskLockHeldError: The key was still held when ``wait_seconds``
                elapsed.
        """
        owner = holder or default_holder_id()
        # The wait deadline is measured with the monotonic clock, not the
        # injectable one: a timeout must not be extendable by a clock that the
        # caller (or a test) can move.
        deadline = time.monotonic() + max(0.0, wait_seconds)
        while True:
            if await self.acquire(key, owner, ttl_seconds, **extra):
                return DatabaseLockHandle(self, key, owner, ttl_seconds)
            if time.monotonic() >= deadline:
                snapshot = await self.snapshot(key)
                raise TaskLockHeldError(
                    f"Lock {key!r} is still held after waiting {wait_seconds}s",
                    details={
                        "key": key,
                        "holder": snapshot.holder,
                        "ttl_remaining": round(snapshot.ttl_remaining, 3),
                    },
                    hint="Increase wait_seconds, or check whether the holder crashed "
                    "(its lock expires at locked_until).",
                )
            await asyncio.sleep(poll_interval)

    @asynccontextmanager
    async def guard(
        self,
        key: str,
        *,
        holder: str | None = None,
        ttl_seconds: float = 60.0,
        skip_on_contention: bool = True,
        **extra: Any,
    ) -> AsyncGenerator[DatabaseLockHandle | None, None]:
        """Run a block only when the key is free, skipping it otherwise.

        This is the shape scheduled work wants: a second instance arriving at
        the same cron tick should do nothing rather than queue behind the
        first. When ``skip_on_contention`` is ``False`` the behaviour matches
        :meth:`hold` and raises instead.

        Args:
            key: The lock key.
            holder: Holder id (a process identity is generated when omitted).
            ttl_seconds: How long each claim lasts.
            skip_on_contention: Yield ``None`` instead of raising.
            **extra: Values for the configured ``extra_columns``.

        Yields:
            The handle, or ``None`` when another instance holds the key and
            ``skip_on_contention`` is set.

        Raises:
            TaskLockHeldError: The key is held and ``skip_on_contention`` is
                ``False``.
        """
        owner = holder or default_holder_id()
        acquired = await self.acquire(key, owner, ttl_seconds, **extra)
        if not acquired:
            if not skip_on_contention:
                snapshot = await self.snapshot(key)
                raise TaskLockHeldError(
                    f"Lock {key!r} is held by another instance",
                    details={"key": key, "holder": snapshot.holder},
                    hint="Retry after the holder finishes or its lock expires.",
                )
            logger.debug("db_lock.skipped", key=key, table=self._table)
            yield None
            return

        handle = DatabaseLockHandle(self, key, owner, ttl_seconds)
        try:
            yield handle
        finally:
            await handle.release()

    def describe(self, extras: Mapping[str, object] | None = None) -> dict[str, object]:
        """Return a log-friendly description of this manager's configuration.

        Args:
            extras: Optional extra columns to include in the result.

        Returns:
            A dict with the table, columns and provider surface.
        """
        description: dict[str, object] = {
            "table": self._table,
            "key_column": self._key_column,
            "holder_column": self._holder_column,
            "until_column": self._until_column,
            "extra_columns": list(self._extra_columns),
            "surface": self._runner.surface,
        }
        if extras:
            description["config"] = dict(extras)
        return description
