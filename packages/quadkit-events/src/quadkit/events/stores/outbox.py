"""Transactional Outbox implementation (MF-02).

This module provides the OutboxEventStore decorator and OutboxPublisher
for reliable event publishing using the Outbox pattern.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from quadkit.events.stores.base import AbstractEventStore
from quadkit.identity import ambient as ambient_identity
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.events.buses.event import EventBusImpl
    from quadkit.events.messages.event import Event

logger = get_logger(__name__)


class OutboxEntryStatus(StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class OutboxEntry:
    """A single entry in the outbox table."""

    entry_id: str = field(default_factory=ambient_identity.new_uuid)
    event_type: str = ""
    payload: str = "{}"
    metadata: str = "{}"
    status: OutboxEntryStatus = OutboxEntryStatus.PENDING
    created_at: datetime = field(default_factory=ambient_clock.now)
    published_at: datetime | None = None
    attempts: int = 0
    error: str | None = None


class OutboxEventStore(AbstractEventStore):
    """Decorator that appends events to an outbox table in the same transaction.

    This decorator works with SQL-based event stores (Postgres, SQLite)
    by participating in their internal transaction when possible.
    """

    def __init__(
        self,
        inner: AbstractEventStore,
        outbox_table: str = "event_outbox",
    ) -> None:
        super().__init__(schema_evolution=getattr(inner, "_schema_evolution", None))
        self.inner = inner
        self.outbox_table = outbox_table

    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Append events to the store and the outbox in a single transaction.

        For SQL-backed stores (Postgres, SQLite) both the event rows and the
        outbox rows are inserted inside the **same** ``provider.transaction()``
        block, giving true ACID atomicity.  The inner store's ``_write_events``
        helper is called directly so no nested transaction is opened.

        For all other store types a warning is emitted and the write falls back
        to a best-effort (non-atomic) two-phase append.
        """
        from quadkit.events.stores.postgres.event_store import PostgresEventStore
        from quadkit.events.stores.sqlite.event_store import SqliteEventStore

        if isinstance(self.inner, (PostgresEventStore, SqliteEventStore)):
            async with self.inner.provider.transaction():
                version = await self.inner._write_events(
                    stream_id, events, expected_version
                )
                await self._append_outbox_rows(self.inner, events)
                return version

        # Fallback for non-SQL stores — no cross-store atomicity guarantee.
        logger.warning(
            "Inner store %s does not support transactional outbox. "
            "Event publishing may be unreliable.",
            type(self.inner).__name__,
        )
        return await self.inner.append(stream_id, events, expected_version)

    async def _append_outbox_rows(
        self,
        inner: Any,
        events: list[Event],
    ) -> None:
        """Insert outbox rows via the inner store's provider (within an active transaction).

        Uses the inner store's ``DatabaseProviderProtocol`` so the inserts share
        the same transaction that was opened by :meth:`append`.

        Args:
            inner: The unwrapped SQL event store (provides ``provider`` and SQL dialect info).
            events: Events whose identity/payload should be captured in the outbox.
        """
        from quadkit.events.stores.postgres.event_store import PostgresEventStore
        from quadkit.serialization import dumps

        # Detect SQL dialect: Postgres uses $N positional params, SQLite uses ?
        if isinstance(inner, PostgresEventStore):
            sql = (
                f"INSERT INTO {self.outbox_table} "  # noqa: S608 — outbox table from init-time ctor arg, never user input
                "(event_id, event_type, event_data, metadata, timestamp, status) "
                "VALUES ($1, $2, $3, $4, $5, 'pending')"
            )
        else:
            sql = (
                f"INSERT INTO {self.outbox_table} "  # noqa: S608 — outbox table from init-time ctor arg, never user input
                "(event_id, event_type, event_data, metadata, timestamp, status) "
                "VALUES (?, ?, ?, ?, ?, 'pending')"
            )

        for event in events:
            event_id = getattr(event, "id", None) or getattr(event, "event_id", None)

            raw = getattr(event, "model_dump", None)
            event_data: dict[str, Any] = raw(mode="json") if raw is not None else {}

            payload = dumps(event_data)
            payload_str = (
                payload.decode("utf-8") if isinstance(payload, bytes) else payload
            )

            meta = getattr(event, "metadata", {})
            if hasattr(meta, "model_dump"):
                meta = meta.model_dump(mode="json")
            meta_raw = dumps(meta)
            meta_str = (
                meta_raw.decode("utf-8") if isinstance(meta_raw, bytes) else meta_raw
            )

            ts = getattr(event, "timestamp", ambient_clock.now())
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

            await inner.provider.execute(
                sql,
                [
                    str(event_id) if event_id else ambient_identity.new_uuid(),
                    type(event).__name__,
                    payload_str,
                    meta_str,
                    ts_str,
                ],
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Any]:
        """Delegate reads to the inner store."""
        return await self.inner.read(stream_id, from_version, to_version, limit)

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> Any:
        """Delegate stream_all to the inner store."""
        async for event in self.inner.stream_all(
            from_position, batch_size, partition, total_partitions
        ):
            yield event

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Delegate compaction to the inner store."""
        return await self.inner.compact(stream_id, up_to_version)

    async def close(self) -> None:
        """Delegate close to the inner store."""
        await self.inner.close()


class OutboxPublisher:
    """Background worker that polls the outbox and publishes events to a bus."""

    def __init__(
        self,
        event_store: AbstractEventStore,
        event_bus: EventBusImpl,
        outbox_table: str = "event_outbox",
        batch_size: int = 100,
        poll_interval: float = 1.0,
    ) -> None:
        self.event_store = event_store
        self.event_bus = event_bus
        self.outbox_table = outbox_table
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Outbox publisher started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Outbox publisher stopped")

    async def _run(self) -> None:
        backoff = self.poll_interval
        while self._running:
            try:
                processed = await self.publish_pending()
                backoff = self.poll_interval
                if processed == 0:
                    await asyncio.sleep(backoff)
            except Exception as e:  # noqa: BLE001 — outbox poll loop; log and back off without stopping the publisher
                logger.exception("Error in outbox publisher loop", error=str(e))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.poll_interval * 32)

    async def publish_pending(self) -> int:
        store = self.event_store
        while hasattr(store, "inner"):
            store = store.inner

        from quadkit.events.stores.postgres.event_store import PostgresEventStore
        from quadkit.events.stores.sqlite.event_store import SqliteEventStore

        if isinstance(store, PostgresEventStore):
            return await self._publish_postgres(store)
        if isinstance(store, SqliteEventStore):
            return await self._publish_sqlite(store)

        return 0

    async def _publish_postgres(self, store: Any) -> int:
        async with store.pool.acquire() as conn:
            rows = await conn.fetch(f"""
                SELECT event_id, event_type, event_data, metadata, timestamp
                FROM {self.outbox_table}
                WHERE status = 'pending'
                ORDER BY timestamp ASC
                LIMIT {self.batch_size}
                FOR UPDATE SKIP LOCKED
            """)  # noqa: S608 — outbox table from init-time ctor arg; batch_size int, never user input

            if not rows:
                return 0

            event_ids = []
            for row in rows:
                try:
                    event = store._deserialize_event(row)
                    await self.event_bus.publish(event)
                    event_ids.append(row["event_id"])
                except Exception as e:  # noqa: BLE001 — per-event isolation; one failed publish must not block remaining outbox events
                    logger.exception(
                        "Failed to publish outbox event %s",
                        row["event_id"],
                        error=str(e),
                    )

            if event_ids:
                await conn.execute(
                    f"""
                    UPDATE {self.outbox_table}
                    SET status = 'published', published_at = $1
                    WHERE event_id = ANY($2)
                """,  # noqa: S608 — outbox table from init-time ctor arg, never user input
                    ambient_clock.now(),
                    event_ids,
                )

            return len(event_ids)

    async def _publish_sqlite(self, store: Any) -> int:
        conn = store.connection
        cursor = await conn.execute(
            f"""
            SELECT event_id, event_type, event_data, metadata, timestamp
            FROM {self.outbox_table}
            WHERE status = 'pending'
            ORDER BY timestamp ASC
            LIMIT ?
        """,  # noqa: S608 — outbox table from init-time ctor arg, never user input
            (self.batch_size,),
        )

        rows = await cursor.fetchall()
        if not rows:
            return 0

        event_ids = []
        for row in rows:
            try:
                row_dict = dict(row)
                event = store.serializer.deserialize_event(row_dict)
                await self.event_bus.publish(event)
                event_ids.append(row_dict["event_id"])
            except Exception as e:  # noqa: BLE001 — per-event isolation (SQLite); one failed publish must not block remaining outbox events
                logger.exception(
                    "Failed to publish outbox event %s", row["event_id"], error=str(e)
                )

        if event_ids:
            placeholders = ", ".join("?" for _ in event_ids)
            await conn.execute(
                f"""
                UPDATE {self.outbox_table}
                SET status = 'published', published_at = ?
                WHERE event_id IN ({placeholders})
            """,  # noqa: S608 — outbox table from init-time ctor arg; placeholders are ? marks, never user input
                (ambient_clock.now().isoformat(), *event_ids),
            )
            await conn.commit()

        return len(event_ids)
