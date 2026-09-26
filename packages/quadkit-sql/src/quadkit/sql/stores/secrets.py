"""Database-backed async secret store.

Persists secrets in a SQL table using the application's shared connection
pool.  For rotation, versioning, or HSM-backed encryption, use
:class:`~quadkit.contracts.security.secrets.SecretStoreProtocol` backed by
a dedicated secret manager (Vault, AWS Secrets Manager, etc.).

Schema (apply via migrations)::

    CREATE TABLE IF NOT EXISTS <table_name> (
        name       TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol


class DatabaseSecretStore:
    """Async secret store backed by the application database.

    Implements :class:`~quadkit.contracts.stores.AsyncSecretStoreProtocol`
    using a SQL table via the shared connection pool from
    :class:`~quadkit.contracts.DatabaseProviderProtocol`.

    Args:
        db_provider: Database provider injected from the DI container.
        table_name: SQL table name used for secret storage.
        auto_create_tables: Reserved — apply DDL via migrations in production.
    """

    def __init__(
        self,
        db_provider: DatabaseProviderProtocol,
        table_name: str = "secrets",
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
                    name       TEXT PRIMARY KEY,
                    value      TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        finally:
            await self._db.release(conn)
        self._table_ensured = True

    async def get(self, name: str) -> str | None:
        """Return the secret value for *name*, or ``None`` if absent."""
        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            row = await conn.fetchrow(
                f"SELECT value FROM {self._table_name} WHERE name = $1",  # noqa: S608 -- self._table_name set at init, values parameterized
                name,
            )
            return row["value"] if row else None
        finally:
            await self._db.release(conn)

    async def get_bulk(self, *names: str) -> dict[str, str]:
        """Return a mapping of name → value for all requested secrets.

        Args:
            names: One or more secret names.

        Returns:
            Dict containing only the names that were found.
        """
        if not names:
            return {}

        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            rows = await conn.fetch(
                f"SELECT name, value FROM {self._table_name} WHERE name = ANY($1)",  # noqa: S608 -- self._table_name set at init, values parameterized
                list(names),
            )
            return {row["name"]: row["value"] for row in rows}
        finally:
            await self._db.release(conn)

    async def set(self, name: str, value: str) -> None:
        """Write or overwrite a secret value."""
        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            await conn.execute(
                f"""
                INSERT INTO {self._table_name} (name, value)
                VALUES ($1, $2)
                ON CONFLICT (name) DO UPDATE SET value = $2, updated_at = NOW()
                """,  # noqa: S608 -- self._table_name set at init, values parameterized
                name,
                value,
            )
        finally:
            await self._db.release(conn)

    async def delete(self, name: str) -> None:
        """Remove a secret.  No-op if absent."""
        await self._ensure_table()
        conn = await self._db.acquire()
        try:
            await conn.execute(
                f"DELETE FROM {self._table_name} WHERE name = $1",  # noqa: S608 -- self._table_name set at init, values parameterized
                name,
            )
        finally:
            await self._db.release(conn)


__all__ = ["DatabaseSecretStore"]
