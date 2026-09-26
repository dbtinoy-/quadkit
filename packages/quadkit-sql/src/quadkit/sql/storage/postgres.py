"""PostgreSQL-backed key-value storage for Quadkit Framework.

This module provides :class:`PostgresStorage`, a :class:`~quadkit.contracts.StorageBackendProtocol`
implementation that stores key-value pairs in a Postgres table with optional
TTL (time-to-live) expiry.

**Role distinction**

:class:`PostgresStorage` is a *storage layer* concept — a key-value /
cache-like abstraction backed by Postgres rows.  It is distinct from
:mod:`quadkit.sql.providers.postgres_provider`, which is a *database
connection layer* that manages Postgres sessions, connection pools, and
query execution.

Use :class:`PostgresStorage` when you need a persistent, queryable
key-value store backed by an existing Postgres database (e.g. for
idempotency records, state, or session data).  Use the Postgres provider
when you need full SQL access via the Quadkit DB abstraction.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from quadkit import serialization as json
from quadkit.contracts.data.identifiers import Table
from quadkit.contracts.infra import StorageBackendProtocol, StorageType
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.sql.providers import DatabaseService

logger = get_logger(__name__)


class PostgresStorage(StorageBackendProtocol):
    """PostgreSQL-backed storage implementation with TTL support."""

    def __init__(
        self,
        db_provider: DatabaseService,
        table_name: str = "storage_kv",
        enable_ttl: bool = True,
    ):
        self.db = db_provider
        self.table_name = table_name
        self._table = Table(table_name)
        self.enable_ttl = enable_ttl
        self._connected = False

    @property
    def storage_type(self) -> StorageType:
        return StorageType.DATABASE

    async def connect(self) -> None:
        """Create storage table if not exists."""
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            namespace VARCHAR(255) DEFAULT 'default',
            key VARCHAR(512) NOT NULL,
            value JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NULL,
            PRIMARY KEY (namespace, key)
        );
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_expires
        ON {self.table_name}(expires_at) WHERE expires_at IS NOT NULL;
        """
        statements = list(filter(None, map(str.strip, create_sql.split(";"))))
        for stmt in statements:
            await self.db.execute_query(stmt)
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def get(self, key: str, namespace: str | None = None) -> Any | None:
        """Get value by key, respecting TTL."""
        ns = namespace or "default"
        sql = f"""
            SELECT value FROM {self._table}
            WHERE namespace = %s AND key = %s
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        """  # noqa: S608 -- self._table is a validated, quoted Table() identifier
        result = await self.db.execute_query(sql, (ns, key))
        rows = getattr(result, "rows", result)
        if not rows:
            return None

        value = rows[0]["value"]
        if isinstance(value, str):
            return json.loads(value)
        return value

    async def set(
        self,
        key: str,
        value: Any,
        namespace: str | None = None,
        ttl: int | None = None,
    ) -> bool:
        """Set value by key with optional TTL."""
        ns = namespace or "default"
        expires_at = None
        if ttl and self.enable_ttl:
            expires_at = (ambient_clock.now()) + timedelta(seconds=ttl)

        sql = f"""
            INSERT INTO {self._table} (namespace, key, value, expires_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (namespace, key)
            DO UPDATE SET
                value = EXCLUDED.value,
                expires_at = EXCLUDED.expires_at,
                created_at = CURRENT_TIMESTAMP
        """  # noqa: S608 -- self._table is a validated, quoted Table() identifier
        val_json = json.dumps(value)
        await self.db.execute_query(sql, (ns, key, val_json, expires_at))
        return True

    async def delete(self, key: str, namespace: str | None = None) -> bool:
        ns = namespace or "default"
        sql = f"DELETE FROM {self._table} WHERE namespace = %s AND key = %s"  # noqa: S608 -- self._table is a validated, quoted Table() identifier
        await self.db.execute_query(sql, (ns, key))
        return True

    async def exists(self, key: str, namespace: str | None = None) -> bool:
        val = await self.get(key, namespace)
        return val is not None

    async def list_keys(
        self,
        pattern: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        ns = namespace or "default"
        if pattern:
            sql_pattern = pattern.replace("*", "%").replace("?", "_")
            sql = f"""
                SELECT key FROM {self._table}
                WHERE namespace = %s AND key LIKE %s
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """  # noqa: S608 -- self._table is a validated, quoted Table() identifier
            result = await self.db.execute_query(sql, (ns, sql_pattern))
        else:
            sql = f"""
                SELECT key FROM {self._table}
                WHERE namespace = %s
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """  # noqa: S608 -- self._table is a validated, quoted Table() identifier
            result = await self.db.execute_query(sql, (ns,))

        rows = getattr(result, "rows", result)
        return [row["key"] for row in rows]

    async def clear(self, namespace: str | None = None) -> bool:
        ns = namespace or "default"
        sql = f"DELETE FROM {self._table} WHERE namespace = %s"  # noqa: S608 -- self._table is a validated, quoted Table() identifier
        await self.db.execute_query(sql, (ns,))
        return True

    async def cleanup_expired(self) -> int:
        """Manually trigger cleanup of expired records."""
        sql = f"""
            DELETE FROM {self._table}
            WHERE expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP
        """  # noqa: S608 -- self._table is a validated, quoted Table() identifier
        result = await self.db.execute_query(sql)
        return getattr(result, "rowcount", 0)
