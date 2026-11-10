"""Transactional Outbox implementation (MF-02).

This module provides the OutboxEventStore decorator and OutboxPublisher
for reliable event publishing using the Outbox pattern.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from inspect import iscoroutinefunction
import math
from typing import TYPE_CHECKING, Any, Protocol, cast
from uuid import UUID

from pydantic import TypeAdapter

from quadkit.contracts.data.identifiers import Table
from quadkit.contracts.data.sql.committed_reads import (
    CommittedReadGuardProtocol,
    CommittedReadState,
)
from quadkit.contracts.domain import DomainEvent
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.base import AbstractEventStore
from quadkit.identity import ambient as ambient_identity
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from quadkit.events.buses.event import EventBusImpl
    from quadkit.events.messages.event import Event
    from quadkit.events.types import StreamInfo

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
        self._outbox_table = Table(outbox_table)
        self.outbox_table = outbox_table

    async def get_stream_version(self, stream_id: str) -> int:
        """Delegate the logical stream version to the wrapped store."""
        return await self.inner.get_stream_version(stream_id)

    async def stream_exists(self, stream_id: str) -> bool:
        """Delegate stream existence to the wrapped store."""
        return await self.inner.stream_exists(stream_id)

    async def get_stream_info(self, stream_id: str) -> StreamInfo | None:
        """Delegate stream information to the wrapped store."""
        return await self.inner.get_stream_info(stream_id)

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

        For other store types a warning is emitted and only the inner store is
        written; no outbox row is staged. Do not rely on that fallback for
        event delivery.
        """
        from quadkit.events.stores.postgres.event_store import PostgresEventStore
        from quadkit.events.stores.sqlite.event_store import SqliteEventStore

        if isinstance(self.inner, (PostgresEventStore, SqliteEventStore)):
            async with self.inner.provider.transaction():
                if isinstance(self.inner, PostgresEventStore) and events:
                    # Match the inner store's stream serialization before checking
                    # the version; _write_events intentionally does not lock.
                    lock = await self.inner.provider.execute(
                        "SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))",
                        [stream_id],
                    )
                    if not lock.success:
                        raise EventStoreError("Could not lock event stream")
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
                f"INSERT INTO {self._outbox_table} "  # noqa: S608 — outbox table from init-time ctor arg, never user input
                "(event_id, event_type, event_data, metadata, timestamp, status) "
                "VALUES ($1, $2, $3, $4, $5, 'pending')"
            )
        else:
            sql = (
                f"INSERT INTO {self._outbox_table} "  # noqa: S608 — outbox table from init-time ctor arg, never user input
                "(event_id, event_type, event_data, metadata, timestamp, status) "
                "VALUES (?, ?, ?, ?, ?, 'pending')"
            )

        for event in events:
            event_id = getattr(event, "id", None) or getattr(event, "event_id", None)

            # Use exactly the same representation as the event store, including
            # custom serializers. Generated events are dataclasses, not models.
            event_data = (
                inner._serialize_event(event)
                if isinstance(inner, PostgresEventStore)
                else inner.serializer.serialize_event(event)
            )

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

            ts = (
                getattr(event, "timestamp", None)
                or getattr(event, "occurred_at", None)
                or ambient_clock.now()
            )
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

            result = await inner.provider.execute(
                sql,
                [
                    str(event_id) if event_id else ambient_identity.new_uuid(),
                    type(event).__name__,
                    payload_str,
                    meta_str,
                    ts_str,
                ],
            )
            if not result.success:
                raise EventStoreError("Could not write outbox event")

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


class AcknowledgedEventSink(Protocol):
    """Durable handoff for at-least-once outbox delivery.

    Return None only after the event is durably accepted; raise on failure.
    A process-local EventBusImpl queue does not meet this contract. The same
    event may be delivered again, so the destination must deduplicate by its
    event_id or otherwise tolerate retries.
    """

    async def deliver(self, event: DomainEvent) -> object: ...


class OutboxPublisher:
    """Relay committed SQLite outbox entries to an acknowledged durable sink.

    The legacy ``event_bus`` argument is retained for source compatibility but
    cannot acknowledge durable delivery and is never used as a sink. SQL relay
    calls require an explicit ``acknowledged_sink``. PostgreSQL relay support is
    refused until its transaction and deserialization paths are verified.

    The relay is at-least-once, not exactly-once: crashes or concurrent relays
    can hand off the same event more than once. The sink must deduplicate by
    event ID. Publication inside an existing database transaction is refused
    so an uncommitted outbox entry cannot escape a subsequent rollback.
    """

    def __init__(
        self,
        event_store: AbstractEventStore,
        event_bus: EventBusImpl | None = None,
        outbox_table: str = "event_outbox",
        batch_size: int = 100,
        poll_interval: float = 1.0,
        *,
        acknowledged_sink: AcknowledgedEventSink | None = None,
    ) -> None:
        if (
            isinstance(batch_size, bool)
            or not isinstance(batch_size, int)
            or batch_size < 1
        ):
            raise ValueError("batch_size must be a positive integer")
        if (
            isinstance(poll_interval, bool)
            or not math.isfinite(poll_interval)
            or poll_interval <= 0
        ):
            raise ValueError("poll_interval must be finite and positive")
        self.event_store = event_store
        self.event_bus = event_bus
        self._outbox_table = Table(outbox_table)
        self.outbox_table = outbox_table
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.acknowledged_sink = acknowledged_sink
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._running:
            return
        if type(self).publish_pending is OutboxPublisher.publish_pending:
            store = self._check_backend()
            from quadkit.events.stores.sqlite.event_store import SqliteEventStore

            if isinstance(store, SqliteEventStore):
                self._ensure_outside_transaction(store.provider)
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
            except Exception as e:  # noqa: BLE001 — poll loop logs and backs off
                logger.exception("Error in outbox publisher loop", error=str(e))
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self.poll_interval * 32)

    def _check_backend(self) -> AbstractEventStore:
        store = self.event_store
        while hasattr(store, "inner"):
            store = store.inner

        from quadkit.events.stores.postgres.event_store import PostgresEventStore
        from quadkit.events.stores.sqlite.event_store import SqliteEventStore

        if isinstance(store, PostgresEventStore):
            raise EventStoreError("PostgreSQL outbox relay is not verified")
        if isinstance(store, SqliteEventStore):
            if self.acknowledged_sink is None:
                raise EventStoreError("A durable acknowledged event sink is required")
        return store

    async def publish_pending(self) -> int:
        store = self._check_backend()
        from quadkit.events.stores.sqlite.event_store import SqliteEventStore

        if isinstance(store, SqliteEventStore):
            return await self._publish_sqlite(store)
        return 0

    @staticmethod
    def _deserialize_sqlite(store: Any, row: dict[str, Any]) -> DomainEvent:
        serializer = store.serializer
        if serializer.event_serializer:
            event = serializer.deserialize_event(row)
        else:
            event_class = serializer._event_type_registry.get(row["event_type"])
            if (
                not isinstance(event_class, type)
                or not issubclass(event_class, DomainEvent)
                or not is_dataclass(event_class)
                or cast("type", event_class).__name__ != row["event_type"]
            ):
                raise EventStoreError("Outbox event type is not registered")
            payload = loads(row["event_data"])
            if not isinstance(payload, dict):
                raise EventStoreError("Outbox event payload must be an object")
            # Pydantic ignores extra dataclass fields by default; refusing them
            # prevents dynamic Event attributes from disappearing silently.
            if set(payload) - {f.name for f in fields(event_class)}:
                raise EventStoreError("Outbox event has undeclared payload fields")
            event = TypeAdapter(event_class).validate_python(payload)
            if dumps(serializer.serialize_event(event), sort_keys=True) != dumps(
                payload, sort_keys=True
            ):
                raise EventStoreError("Outbox event payload did not round-trip")
        if (
            not isinstance(event, DomainEvent)
            or type(event).__name__ != row["event_type"]
            or not isinstance(event.event_id, UUID)
            or not isinstance(event.occurred_at, datetime)
            or str(event.event_id) != str(row["event_id"])
        ):
            raise EventStoreError("Outbox event identity or type does not match")
        return event

    @staticmethod
    def _ensure_outside_transaction(provider: object) -> None:
        # Adapter-owned checks preserve the import boundary: Events must not
        # certify SQL classes or inspect their private connection machinery.
        # A marker is an opt-in from trusted composition, not plugin attestation.
        if (
            getattr(provider, "supports_committed_read_guard_v1", False) is not True
            or not isinstance(provider, CommittedReadGuardProtocol)
            or not callable(provider.committed_read_state)
            or iscoroutinefunction(provider.committed_read_state)
        ):
            raise EventStoreError("SQLite relay requires a verified SQL provider")
        try:
            state = provider.committed_read_state()
        except Exception as exc:  # noqa: BLE001 -- malformed adapter guards fail closed before reads
            raise EventStoreError("Committed-read safety inspection failed") from exc
        if type(state) is not CommittedReadState:
            raise EventStoreError("SQLite relay requires a verified SQL provider")
        if state is CommittedReadState.SAFE:
            return
        reasons = {
            CommittedReadState.UNSUPPORTED_PROVIDER: "SQLite relay requires a verified SQL provider",
            CommittedReadState.UNSUPPORTED_POOL: "SQLite relay requires a verified connection pool",
            CommittedReadState.UNOBSERVABLE_TRANSACTION: "Outbox requires observable transaction state",
            CommittedReadState.IN_TRANSACTION: "Cannot relay within a database transaction",
        }
        raise EventStoreError(reasons[state])

    async def _publish_sqlite(self, store: Any) -> int:
        provider = store.provider
        self._ensure_outside_transaction(provider)
        result = await provider.execute_query(
            f"SELECT event_id, event_type, event_data, metadata, timestamp "
            f"FROM {self._outbox_table} WHERE status = 'pending' "
            "ORDER BY timestamp ASC, event_id ASC LIMIT ?",  # noqa: S608 — validated Table identifier
            [self.batch_size],
        )
        if not result.success:
            raise EventStoreError("Could not read pending outbox events")

        published = 0
        for row in result.rows:
            try:
                event = self._deserialize_sqlite(store, row)
                assert self.acknowledged_sink is not None
                acknowledgement = await self.acknowledged_sink.deliver(event)
                if acknowledgement is not None:
                    raise EventStoreError("Sink must acknowledge with None or raise")
            except Exception as e:  # noqa: BLE001 — leave failed entries pending and continue
                logger.exception(
                    "Failed to deliver outbox event %s", row["event_id"], error=str(e)
                )
                continue

            update = await provider.execute_update(
                self.outbox_table,
                {
                    "status": "published",
                    "published_at": ambient_clock.now().isoformat(),
                },
                '"event_id" = ? AND "status" = ?',
                [row["event_id"], "pending"],
            )
            if not update.success:
                raise EventStoreError("Could not acknowledge outbox event")
            if update.affected_rows == 1:
                published += 1
            elif update.affected_rows != 0:
                raise EventStoreError("Unexpected outbox acknowledgement count")
        return published
