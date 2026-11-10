"""SQL outbox staging boundaries; this does not exercise relay or app wiring."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from quadkit.contracts.data.sql.database import QueryResult
from quadkit.contracts.domain import DomainEvent
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.outbox import OutboxEventStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.serialization import loads
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@dataclass(frozen=True, kw_only=True)
class OrderSubmitted(DomainEvent):
    order: str
    details: dict


async def setup_stores(pooled: bool, serializer=None):
    pool = SQLiteConnectionPool(":memory:") if pooled else None
    db = SQLiteProvider(":memory:", connection_pool=pool)
    await db.connect()
    store = SqliteEventStore(provider=db, event_serializer=serializer)
    await store.connect()
    await db.execute_query(
        """CREATE TABLE event_outbox (
            event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
            event_data TEXT NOT NULL, metadata TEXT NOT NULL,
            timestamp TEXT NOT NULL, status TEXT NOT NULL, published_at TEXT
        )"""
    )
    return db, OutboxEventStore(store)


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_generated_dataclass_payload_staged_with_event(pooled):
    db, store = await setup_stores(pooled)
    event = OrderSubmitted(
        aggregate_id=uuid4(), order="order-42", details={"items": [1, 2]}
    )
    try:
        assert await store.append("orders-42", [event], expected_version=0) == 1
        events = (await db.execute_query("SELECT * FROM events")).rows
        outbox = (await db.execute_query("SELECT * FROM event_outbox")).rows
        assert len(events) == len(outbox) == 1
        staged = outbox[0]
        assert staged["event_id"] == events[0]["event_id"] == str(event.event_id)
        assert staged["event_type"] == events[0]["event_type"] == "OrderSubmitted"
        assert loads(staged["event_data"]) == loads(events[0]["event_data"])
        assert loads(staged["event_data"])["order"] == "order-42"
        assert loads(staged["event_data"])["details"] == {"items": [1, 2]}
        assert staged["timestamp"] == event.occurred_at.isoformat()
        assert staged["status"] == "pending"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_outbox_uses_custom_event_serializer():
    class Serializer:
        def serialize(self, event):
            return {"serialized_order": event.order}

    db, store = await setup_stores(False, Serializer())
    try:
        await store.append("orders", [OrderSubmitted(order="special", details={})])
        event = (await db.execute_query("SELECT event_data FROM events")).rows[0]
        staged = (await db.execute_query("SELECT event_data FROM event_outbox")).rows[0]
        assert (
            loads(staged["event_data"])
            == loads(event["event_data"])
            == {"serialized_order": "special"}
        )
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
@pytest.mark.parametrize("failed_table", ["events", "event_outbox"])
async def test_reported_failed_write_rolls_back_both_rows(pooled, failed_table):
    db, store = await setup_stores(pooled)
    original_execute = db.execute

    async def reported_failure(sql, params=None):
        result = await original_execute(sql, params)
        # Simulate a provider returning an error result even after writing.
        if sql.lstrip().startswith(f'INSERT INTO "{failed_table}"'):
            return QueryResult([], 0, 0.0, False, "private database detail")
        return result

    db.execute = reported_failure
    try:
        with pytest.raises(EventStoreError, match="Could not write"):
            await store.append("orders", [OrderSubmitted(order="x", details={})])
        assert (await db.execute_query("SELECT * FROM events")).rows == []
        assert (await db.execute_query("SELECT * FROM event_outbox")).rows == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_outer_transaction_rollback_includes_both_staged_rows(pooled):
    db, store = await setup_stores(pooled)
    try:
        with pytest.raises(ValueError, match="abort"):  # noqa: PT012
            async with db.transaction():
                await store.append("orders", [OrderSubmitted(order="x", details={})])
                raise ValueError("abort")
        assert (await db.execute_query("SELECT * FROM events")).rows == []
        assert (await db.execute_query("SELECT * FROM event_outbox")).rows == []
    finally:
        await db.disconnect()


def test_outbox_table_name_must_be_safe():
    from quadkit.contracts.data.sql.sql import InvalidIdentifierError
    from quadkit.events.stores.memory import InMemoryEventStore

    with pytest.raises(InvalidIdentifierError):
        OutboxEventStore(InMemoryEventStore(), "outbox; DROP TABLE events")


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_entity_and_event_writes_share_outer_rollback(pooled):
    db, store = await setup_stores(pooled)
    try:
        await db.execute_query("CREATE TABLE orders (id TEXT PRIMARY KEY, status TEXT)")
        await db.execute_insert("orders", {"id": "one", "status": "draft"})
        with pytest.raises(ValueError, match="abort"):  # noqa: PT012
            async with db.transaction():
                await db.execute_update(
                    "orders", {"status": "submitted"}, '"id" = ?', ["one"]
                )
                await store.append(
                    "orders-one", [OrderSubmitted(order="one", details={})]
                )
                raise ValueError("abort")
        assert (await db.execute_query("SELECT status FROM orders")).rows[0][
            "status"
        ] == "draft"
        assert (await db.execute_query("SELECT * FROM events")).rows == []
        assert (await db.execute_query("SELECT * FROM event_outbox")).rows == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_version_read_failure_cannot_be_treated_as_empty_stream():
    db, store = await setup_stores(False)
    original_query = db.execute_query

    async def failed_version_read(sql, params=None):
        if "MAX(stream_version)" in sql:
            return QueryResult([], 0, 0.0, False, "private database detail")
        return await original_query(sql, params)

    db.execute_query = failed_version_read
    try:
        with pytest.raises(
            EventStoreError, match="Could not read event stream version"
        ):
            await store.append("orders", [OrderSubmitted(order="x", details={})])
        assert (await db.execute_query("SELECT * FROM events")).rows == []
        assert (await db.execute_query("SELECT * FROM event_outbox")).rows == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_sqlite_schema_uses_valid_indexes_for_custom_table_names():
    from quadkit.events.config import SqliteConfig
    from quadkit.events.stores.sqlite.queries import SqliteQueries

    db = SQLiteProvider(":memory:")
    await db.connect()
    try:
        queries = SqliteQueries(
            SqliteConfig(events_table="order_events", snapshots_table="order_snapshots")
        )
        for ddl in (
            queries.get_create_events_table_sql(),
            queries.get_create_snapshots_table_sql(),
        ):
            for statement in ddl.split(";"):
                if statement.strip():
                    await db.execute_query(statement)
        indexes = await db.execute_query(
            "SELECT name FROM sqlite_master WHERE type = 'index'"
        )
        names = {row["name"] for row in indexes.rows}
        assert "idx_order_events_stream_id" in names
        assert "idx_order_events_event_type" in names
        assert "idx_order_events_timestamp" in names
        assert "idx_order_snapshots_aggregate_id" in names
    finally:
        await db.disconnect()
