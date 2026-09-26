"""Implementation of AbstractIdempotencyStore (M-17)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.events.stores.base import AbstractIdempotencyStore
from quadkit.events.stores.identifiers import validate_table_name
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from uuid import UUID


class SqlIdempotencyStore(AbstractIdempotencyStore):
    """SQL implementation of AbstractIdempotencyStore for Postgres and SQLite."""

    def __init__(self, connection: Any, table_name: str = "event_idempotency") -> None:
        validate_table_name(table_name)
        self.connection = connection
        self.table_name = table_name

    async def is_processed(self, consumer_id: str, message_id: str | UUID) -> bool:
        """Check if a message has already been processed by a consumer."""
        is_asyncpg = hasattr(self.connection, "fetchval")
        msg_id_str = str(message_id)

        if is_asyncpg:
            query = f"""
                SELECT 1 FROM {self.table_name}
                WHERE consumer_id = $1 AND message_id = $2
            """  # noqa: S608 — table name validated by validate_table_name at init
            val = await self.connection.fetchval(query, consumer_id, msg_id_str)
        else:
            query = f"""
                SELECT 1 FROM {self.table_name}
                WHERE consumer_id = ? AND message_id = ?
            """  # noqa: S608 — table name validated by validate_table_name at init
            cursor = await self.connection.execute(query, (consumer_id, msg_id_str))
            row = await cursor.fetchone()
            val = row[0] if row else None

        return val is not None

    async def mark_processed(
        self,
        consumer_id: str,
        message_id: str | UUID,
        expires_in: float | None = None,
    ) -> None:
        """Mark a message as processed by a consumer."""
        is_asyncpg = hasattr(self.connection, "execute")
        msg_id_str = str(message_id)
        expires_at = None
        if expires_in is not None:
            expires_at = ambient_clock.timestamp() + expires_in

        if is_asyncpg:
            query = f"""
                INSERT INTO {self.table_name} (consumer_id, message_id, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (consumer_id, message_id) DO UPDATE SET expires_at = $3
            """  # noqa: S608 — table name validated by validate_table_name at init
            await self.connection.execute(query, consumer_id, msg_id_str, expires_at)
        else:
            query = f"""
                INSERT OR REPLACE INTO {self.table_name} (consumer_id, message_id, expires_at)
                VALUES (?, ?, ?)
            """  # noqa: S608 — table name validated by validate_table_name at init
            await self.connection.execute(query, (consumer_id, msg_id_str, expires_at))
            await self.connection.commit()

    async def clear_expired(self) -> int:
        """Clear expired idempotency entries."""
        is_asyncpg = hasattr(self.connection, "execute")
        now = ambient_clock.timestamp()

        if is_asyncpg:
            res = await self.connection.execute(
                f"DELETE FROM {self.table_name} WHERE expires_at IS NOT NULL AND expires_at < $1",  # noqa: S608 — table name validated by validate_table_name at init
                now,
            )
            # asyncpg execute returns a status string like "DELETE 5"
            try:
                return int(res.split()[-1])
            except (ValueError, IndexError):
                return 0
        else:
            cursor = await self.connection.execute(
                f"DELETE FROM {self.table_name} WHERE expires_at IS NOT NULL AND expires_at < ?",  # noqa: S608 — table name validated by validate_table_name at init
                (now,),
            )
            await self.connection.commit()
            count: int = cursor.rowcount
            return count

    async def close(self) -> None:
        """Close the store. No-op: the injected connection is owned by the caller."""


class InMemoryIdempotencyStore(AbstractIdempotencyStore):
    """In-memory implementation of AbstractIdempotencyStore."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], float | None] = {}

    async def is_processed(self, consumer_id: str, message_id: str | UUID) -> bool:
        entry = self._entries.get((consumer_id, str(message_id)))
        if entry is None:
            return False

        if entry is not None and entry < ambient_clock.timestamp():
            del self._entries[(consumer_id, str(message_id))]
            return False

        return True

    async def mark_processed(
        self,
        consumer_id: str,
        message_id: str | UUID,
        expires_in: float | None = None,
    ) -> None:
        expires_at = None
        if expires_in is not None:
            expires_at = ambient_clock.timestamp() + expires_in
        self._entries[(consumer_id, str(message_id))] = expires_at

    async def clear_expired(self) -> int:
        now = ambient_clock.timestamp()
        to_delete = [k for k, v in self._entries.items() if v is not None and v < now]
        for k in to_delete:
            del self._entries[k]
        return len(to_delete)

    async def close(self) -> None:
        """Close the store and release resources."""
        self._entries.clear()
