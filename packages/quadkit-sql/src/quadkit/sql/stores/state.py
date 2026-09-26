"""Database-backed state store.

Backed by the application's own connection pool via
:class:`~quadkit.contracts.DatabaseProviderProtocol`, so no extra
connection overhead is introduced.

Schema (auto-created when ``auto_create_tables=True``)::

    CREATE TABLE IF NOT EXISTS <table_name> (
        key       TEXT PRIMARY KEY,
        value     TEXT NOT NULL,
        expires_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol


class DatabaseStateStore:
    """State store that uses quadkit-sql's DatabaseService for connections.

    Shares the application's connection pool with the main application path,
    participates in DatabaseService health monitoring, and is driven by the
    same connection configuration as the rest of the application.

    Args:
        db_provider: Database provider injected from the DI container.
        table_name: SQL table name used for state storage.
        auto_create_tables: Reserved — table DDL should be applied via
            migrations in production.
    """

    def __init__(
        self,
        db_provider: DatabaseProviderProtocol,
        table_name: str = "app_state",
        auto_create_tables: bool = True,
    ) -> None:
        self._db = db_provider
        self._table_name = table_name
        self._auto_create = auto_create_tables
        self._table_ensured = False

    async def _ensure_table(self) -> None:
        """Create the store's table on first use when auto-create is enabled."""
        if not self._auto_create or self._table_ensured:
            return
        conn = await self._db.acquire()
        try:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    key        TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    expires_at TIMESTAMPTZ,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        finally:
            await self._db.release(conn)
        self._table_ensured = True

    async def get(self, key: str) -> Any | None:
        """Return the value stored under *key*, or ``None`` if absent."""
        await self._ensure_table()
        from quadkit import serialization as json

        conn = await self._db.acquire()
        try:
            row = await conn.fetchrow(
                f"SELECT value FROM {self._table_name} WHERE key = $1",  # noqa: S608 -- table name from init-time config, values parameterized
                key,
            )
            if row and row.get("value"):
                return json.loads(row["value"])
            return None
        finally:
            await self._db.release(conn)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> None:
        """Persist *value* under *key* with an optional TTL in seconds."""
        await self._ensure_table()
        from quadkit import serialization as json

        conn = await self._db.acquire()
        try:
            value_json = json.dumps(value)

            if ttl:
                from datetime import timedelta

                now = ambient_clock.now()
                expires_at = now + timedelta(seconds=ttl)
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (key, value, expires_at)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (key) DO UPDATE
                    SET value = $2, expires_at = $3, updated_at = NOW()
                    """,  # noqa: S608 -- table name from init-time config, values parameterized
                    key,
                    value_json,
                    expires_at,
                )
            else:
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (key, value)
                    VALUES ($1, $2)
                    ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
                    """,  # noqa: S608 -- table name from init-time config, values parameterized
                    key,
                    value_json,
                )
        finally:
            await self._db.release(conn)

    async def delete(self, key: str) -> None:
        """Remove the entry for *key*.  No-op if absent."""
        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            await conn.execute(
                f"DELETE FROM {self._table_name} WHERE key = $1",  # noqa: S608 -- table name from init-time config, values parameterized
                key,
            )
        finally:
            await self._db.release(conn)

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Fetch multiple keys in a single query.

        Args:
            keys: List of storage keys.

        Returns:
            Dict of found key → deserialized value; absent keys are omitted.
        """
        from quadkit import serialization as json

        if not keys:
            return {}

        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            rows = await conn.fetch(
                f"SELECT key, value FROM {self._table_name} WHERE key = ANY($1)",  # noqa: S608 -- table name from init-time config, values parameterized
                keys,
            )
            return {
                row["key"]: json.loads(row["value"]) for row in rows if row.get("value")
            }
        finally:
            await self._db.release(conn)

    async def set_many(
        self,
        items: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Persist multiple key-value pairs.

        Args:
            items: Mapping of key → JSON-serializable value.
            ttl: Optional TTL in seconds applied to every entry.
        """
        from quadkit import serialization as json

        if not items:
            return

        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            for key, value in items.items():
                value_json = json.dumps(value)

                if ttl:
                    from datetime import timedelta

                    now = ambient_clock.now()
                    expires_at = now + timedelta(seconds=ttl)
                    await conn.execute(
                        f"""
                        INSERT INTO {self._table_name} (key, value, expires_at)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (key) DO UPDATE
                        SET value = $2, expires_at = $3, updated_at = NOW()
                        """,  # noqa: S608 -- table name from init-time config, values parameterized
                        key,
                        value_json,
                        expires_at,
                    )
                else:
                    await conn.execute(
                        f"""
                        INSERT INTO {self._table_name} (key, value)
                        VALUES ($1, $2)
                        ON CONFLICT (key) DO UPDATE SET value = $2, updated_at = NOW()
                        """,  # noqa: S608 -- table name from init-time config, values parameterized
                        key,
                        value_json,
                    )
        finally:
            await self._db.release(conn)


__all__ = ["DatabaseStateStore"]
