"""Database-backed distributed lock store.

Uses optimistic INSERT + conflict detection to provide advisory distributed
locks backed by the application's database.  For high-volume locking workloads
consider Redis-backed locks instead.

Schema (apply via migrations)::

    CREATE TABLE IF NOT EXISTS <table_name> (
        lock_name  TEXT PRIMARY KEY,
        owner      TEXT NOT NULL,
        expires_at TIMESTAMPTZ NOT NULL
    );
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, cast

from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol


class DatabaseLockStore:
    """Persistent distributed lock store backed by a SQL table.

    Implements :class:`~quadkit.contracts.stores.LockStoreProtocol` using
    the application's shared connection pool.  Expired locks are lazily
    reclaimed on the next ``acquire()`` attempt.

    Args:
        db_provider: Database provider injected from the DI container.
        table_name: SQL table name used for lock storage.
        auto_create_tables: Reserved — apply DDL via migrations in production.
        clock: Clock for timestamps.
    """

    def __init__(
        self,
        db_provider: DatabaseProviderProtocol,
        table_name: str = "locks",
        auto_create_tables: bool = True,
    ) -> None:
        self._db = db_provider
        self._table_name = table_name
        self._auto_create = auto_create_tables
        self._table_ensured = False

    @property
    def _now(self) -> datetime:
        """Get current time using ambient clock."""
        return ambient_clock.now()

    async def _ensure_table(self) -> None:
        """Create the store's table on first use when auto-create is enabled."""
        if not self._auto_create or self._table_ensured:
            return
        conn = await self._db.acquire()
        try:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    lock_name  TEXT PRIMARY KEY,
                    owner      TEXT NOT NULL,
                    expires_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        finally:
            await self._db.release(conn)
        self._table_ensured = True

    async def acquire(
        self,
        lock_name: str,
        owner: str,
        ttl: int,
    ) -> bool:
        """Attempt to acquire the named lock.

        Returns ``True`` if the lock was acquired (or reclaimed after expiry);
        ``False`` if a non-expired lock already exists under a different owner.
        """
        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            expires_at = self._now + timedelta(seconds=ttl)

            # Attempt an optimistic insert.  ON CONFLICT DO NOTHING lets us check
            # the result tag to determine whether we won the race.
            # The driver connection returns a command tag (e.g. ``INSERT 0 1``)
            # for DML; the contracts typing models it as ``QueryResult``.
            cmd_tag: str = cast(
                "str",
                await conn.execute(
                    f"""
                INSERT INTO {self._table_name} (lock_name, owner, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (lock_name) DO NOTHING
                """,  # noqa: S608 -- self._table_name set at init, values parameterized
                    lock_name,
                    owner,
                    expires_at,
                ),
            )

            if cmd_tag == "INSERT 0 1":
                return True

            # Lock exists — check whether it has expired.
            row = await conn.fetchrow(
                f"SELECT expires_at FROM {self._table_name} WHERE lock_name = $1",  # noqa: S608 -- self._table_name set at init, values parameterized
                lock_name,
            )

            if row and row["expires_at"] < self._now:
                # Expired — attempt to claim it atomically.
                cmd_tag = cast(
                    "str",
                    await conn.execute(
                        f"""
                    UPDATE {self._table_name}
                    SET owner = $2, expires_at = $3
                    WHERE lock_name = $1 AND expires_at < NOW()
                    """,  # noqa: S608 -- self._table_name set at init, values parameterized
                        lock_name,
                        owner,
                        expires_at,
                    ),
                )
                return cmd_tag != "UPDATE 0"

            return False
        finally:
            await self._db.release(conn)

    async def release(self, lock_name: str, owner: str) -> bool:
        """Release the lock *only if* it is held by *owner*.

        Returns ``True`` if the lock was released; ``False`` if it was not
        held by *owner* or did not exist.
        """
        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            cmd_tag = cast(
                "str",
                await conn.execute(
                    f"""
                DELETE FROM {self._table_name}
                WHERE lock_name = $1 AND owner = $2
                """,  # noqa: S608 -- self._table_name set at init, values parameterized
                    lock_name,
                    owner,
                ),
            )
            return cmd_tag != "DELETE 0"
        finally:
            await self._db.release(conn)

    async def extend(
        self,
        lock_name: str,
        owner: str,
        ttl: int,
    ) -> bool:
        """Extend the TTL of a currently-held lock.

        Returns ``True`` if the extension was applied; ``False`` if the lock
        is not held by *owner*.
        """
        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            new_expires_at = self._now + timedelta(seconds=ttl)
            cmd_tag = cast(
                "str",
                await conn.execute(
                    f"""
                UPDATE {self._table_name}
                SET expires_at = $3
                WHERE lock_name = $1 AND owner = $2
                """,  # noqa: S608 -- self._table_name set at init, values parameterized
                    lock_name,
                    owner,
                    new_expires_at,
                ),
            )
            return cmd_tag != "UPDATE 0"
        finally:
            await self._db.release(conn)


__all__ = ["DatabaseLockStore"]
