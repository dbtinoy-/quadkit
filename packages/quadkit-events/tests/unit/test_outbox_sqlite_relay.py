"""SQLite staging/relay components with a deliberately explicit sink double.

The double is not evidence that any production sink is durable.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

import pytest
from test_outbox_sqlite_staging import setup_stores

from quadkit.contracts.domain import DomainEvent
from quadkit.events.buses.event import EventBusImpl
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores import OutboxPublisher
from quadkit.result import Err


@dataclass(frozen=True, kw_only=True)
class OrderApproved(DomainEvent):
    order_id: UUID
    approved_on: date
    info: dict


@dataclass(frozen=True, kw_only=True)
class Nested:
    known: int


@dataclass(frozen=True, kw_only=True)
class NestedEvent(DomainEvent):
    payload: Nested


class Sink:
    def __init__(self):
        self.received = []
        self.fail = False

    async def deliver(self, event):
        if self.fail:
            raise RuntimeError("sink unavailable")
        self.received.append(event)


async def rows(db):
    return (await db.execute_query("SELECT * FROM event_outbox ORDER BY event_id")).rows


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_registered_event_delivered_with_typed_payload_after_ack(pooled):
    db, store = await setup_stores(pooled)
    event = OrderApproved(
        order_id=uuid4(), approved_on=date(2025, 10, 2), info={"n": 4}
    )
    store.register_event_type("OrderApproved", OrderApproved)
    sink = Sink()
    relay = OutboxPublisher(store, EventBusImpl(), acknowledged_sink=sink)
    try:
        await store.append("orders", [event])
        assert await relay.publish_pending() == 1
        assert sink.received == [event]
        assert isinstance(sink.received[0].event_id, UUID)
        assert isinstance(sink.received[0].occurred_at, datetime)
        assert isinstance(sink.received[0].order_id, UUID)
        assert isinstance(sink.received[0].approved_on, date)
        assert (await rows(db))[0]["status"] == "published"
        assert (await rows(db))[0]["published_at"] is not None
        assert await relay.publish_pending() == 0
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_bus_enqueue_alone_cannot_acknowledge_and_unregistered_stays_pending():
    db, store = await setup_stores(False)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    relay = OutboxPublisher(store, EventBusImpl())
    sink = Sink()
    try:
        await store.append("orders", [event])
        with pytest.raises(EventStoreError, match="durable acknowledged"):
            await relay.publish_pending()
        relay.acknowledged_sink = sink
        assert await relay.publish_pending() == 0
        assert sink.received == []
        assert (await rows(db))[0]["status"] == "pending"
        store.register_event_type("OrderApproved", OrderApproved)
        assert await relay.publish_pending() == 1
        assert sink.received == [event]
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_sink_failure_and_non_none_return_leave_pending():
    db, store = await setup_stores(False)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    sink = Sink()
    sink.fail = True
    relay = OutboxPublisher(store, None, acknowledged_sink=sink)
    try:
        await store.append("orders", [event])
        assert await relay.publish_pending() == 0
        assert (await rows(db))[0]["status"] == "pending"

        class BadSink:
            async def deliver(self, event):
                return Err(RuntimeError("rejected"))

        relay.acknowledged_sink = BadSink()
        assert await relay.publish_pending() == 0
        assert (await rows(db))[0]["status"] == "pending"
        sink.fail = False
        relay.acknowledged_sink = sink
        assert await relay.publish_pending() == 1
        assert sink.received == [event]
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_uncommitted_rows_cannot_be_relayed():
    db, store = await setup_stores(False)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    sink = Sink()
    relay = OutboxPublisher(store, None, acknowledged_sink=sink)
    try:
        with pytest.raises(ValueError, match="abort"):  # noqa: PT012
            async with db.transaction():
                await store.append("orders", [event])
                with pytest.raises(
                    EventStoreError, match="within a database transaction"
                ):
                    await relay.publish_pending()
                raise ValueError("abort")
        assert sink.received == []
        assert await rows(db) == []
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_failed_status_update_causes_retry_and_duplicate_handoff():
    db, store = await setup_stores(False)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    sink = Sink()
    relay = OutboxPublisher(store, None, acknowledged_sink=sink)
    original = db.execute_update

    async def fail_update(*args, **kwargs):
        raise RuntimeError("update failed")

    try:
        await store.append("orders", [event])
        db.execute_update = fail_update
        with pytest.raises(RuntimeError, match="update failed"):
            await relay.publish_pending()
        assert (await rows(db))[0]["status"] == "pending"
        db.execute_update = original
        assert await relay.publish_pending() == 1
        assert sink.received == [event, event]
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_cancelled_sink_leaves_pending():
    db, store = await setup_stores(False)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})

    class CancelledSink:
        async def deliver(self, event):
            raise asyncio.CancelledError

    try:
        await store.append("orders", [event])
        with pytest.raises(asyncio.CancelledError):
            await OutboxPublisher(
                store, None, acknowledged_sink=CancelledSink()
            ).publish_pending()
        assert (await rows(db))[0]["status"] == "pending"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_mismatched_identity_and_extra_payload_never_reach_sink():
    db, store = await setup_stores(False)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    sink = Sink()
    try:
        await store.append("orders", [event])
        original = (await rows(db))[0]["event_data"]
        await db.execute_update("event_outbox", {"event_id": str(uuid4())}, "1 = 1")
        relay = OutboxPublisher(store, None, acknowledged_sink=sink)
        assert await relay.publish_pending() == 0
        await db.execute_update(
            "event_outbox",
            {
                "event_id": str(event.event_id),
                "event_data": original[:-1] + ',"unexpected":1}',
            },
            "1 = 1",
        )
        assert await relay.publish_pending() == 0
        assert sink.received == []
        assert (await rows(db))[0]["status"] == "pending"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_concurrent_relays_may_deliver_same_event_twice():
    db, store = await setup_stores(True)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    seen = []
    both_called = asyncio.Event()

    class RendezvousSink:
        async def deliver(self, event):
            seen.append(event)
            if len(seen) == 2:
                both_called.set()
            await both_called.wait()

    sink = RendezvousSink()
    try:
        await store.append("orders", [event])
        first = OutboxPublisher(store, None, acknowledged_sink=sink)
        second = OutboxPublisher(store, None, acknowledged_sink=sink)
        counts = await asyncio.wait_for(
            asyncio.gather(first.publish_pending(), second.publish_pending()), timeout=3
        )
        assert sorted(counts) == [0, 1]
        assert seen == [event, event]
        assert (await rows(db))[0]["status"] == "published"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_relay_refuses_unconfigured_sink_on_start_and_postgres():
    from quadkit.events.stores import PostgresEventStore, PostgresEventStoreConfig

    db, store = await setup_stores(False)
    try:
        relay = OutboxPublisher(store, EventBusImpl())
        with pytest.raises(EventStoreError, match="durable acknowledged"):
            await relay.start()
        assert relay._task is None
        postgres = PostgresEventStore(
            PostgresEventStoreConfig(dsn="postgresql://test"), provider=db
        )
        relay = OutboxPublisher(postgres, None, acknowledged_sink=Sink())
        with pytest.raises(
            EventStoreError, match="PostgreSQL outbox relay is not verified"
        ):
            await relay.publish_pending()
        with pytest.raises(
            EventStoreError, match="PostgreSQL outbox relay is not verified"
        ):
            await relay.start()
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_failed_query_and_failed_update_do_not_acknowledge():
    from quadkit.contracts.data.sql.database import QueryResult, UpdateResult

    db, store = await setup_stores(False)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    sink = Sink()
    relay = OutboxPublisher(store, None, acknowledged_sink=sink)
    original_query, original_update = db.execute_query, db.execute_update

    async def bad_query(*args, **kwargs):
        return QueryResult([], 0, 0.0, False, "private")

    async def bad_update(*args, **kwargs):
        return UpdateResult(affected_rows=0, execution_time=0.0, success=False)

    try:
        await store.append("orders", [event])
        db.execute_query = bad_query
        with pytest.raises(EventStoreError, match="Could not read"):
            await relay.publish_pending()
        assert sink.received == []
        db.execute_query = original_query
        db.execute_update = bad_update
        with pytest.raises(EventStoreError, match="Could not acknowledge"):
            await relay.publish_pending()
        assert sink.received == [event]
        assert (await rows(db))[0]["status"] == "pending"
        db.execute_update = original_update
        assert await relay.publish_pending() == 1
        assert sink.received == [event, event]
    finally:
        await db.disconnect()


@pytest.mark.parametrize("invalid", [0, -1, float("nan"), float("inf")])
def test_invalid_poll_interval_rejected(invalid):
    from quadkit.events.stores import InMemoryEventStore

    with pytest.raises(ValueError, match="poll_interval"):
        OutboxPublisher(InMemoryEventStore(), None, poll_interval=invalid)


@pytest.mark.parametrize("invalid", [0, -1, True, 1.5])
def test_invalid_batch_size_rejected(invalid):
    from quadkit.events.stores import InMemoryEventStore

    with pytest.raises(ValueError, match="batch_size"):
        OutboxPublisher(InMemoryEventStore(), None, batch_size=invalid)


@pytest.mark.asyncio
async def test_facade_and_worker_start_refuse_outer_transaction():
    from quadkit.events.stores import OutboxEventStore, SqliteEventStore
    from quadkit.sql.backends.sqlite import SQLiteConnectionPool
    from quadkit.sql.providers.database_service import DatabaseService

    db = DatabaseService(
        "sqlite:///:memory:", connection_pool=SQLiteConnectionPool(":memory:")
    )
    await db.boot()
    try:
        inner = SqliteEventStore(provider=db)
        await inner.connect()
        await db.execute_query("""CREATE TABLE event_outbox (
            event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
            event_data TEXT NOT NULL, metadata TEXT NOT NULL,
            timestamp TEXT NOT NULL, status TEXT NOT NULL, published_at TEXT
        )""")
        inner.register_event_type("OrderApproved", OrderApproved)
        store = OutboxEventStore(inner)
        event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
        sink = Sink()
        relay = OutboxPublisher(store, None, acknowledged_sink=sink)
        with pytest.raises(ValueError, match="abort"):  # noqa: PT012
            async with db.transaction():
                await store.append("orders", [event])
                with pytest.raises(
                    EventStoreError, match="within a database transaction"
                ):
                    await relay.publish_pending()
                with pytest.raises(
                    EventStoreError, match="within a database transaction"
                ):
                    await relay.start()
                raise ValueError("abort")
        assert relay._task is None
        assert sink.received == []
        assert await rows(db) == []
        await store.append("orders", [event])
        assert await relay.publish_pending() == 1
        assert sink.received == [event]
    finally:
        await db.shutdown()


@pytest.mark.asyncio
async def test_nested_payload_data_loss_is_detected():
    from quadkit.serialization import dumps_str, loads

    db, store = await setup_stores(False)
    store.register_event_type("NestedEvent", NestedEvent)
    event = NestedEvent(payload=Nested(known=1))
    sink = Sink()
    try:
        await store.append("orders", [event])
        raw = loads((await rows(db))[0]["event_data"])
        assert (
            OutboxPublisher._deserialize_sqlite(store.inner, (await rows(db))[0])
            == event
        )
        raw["payload"]["extra"] = "must not disappear"
        await db.execute_update("event_outbox", {"event_data": dumps_str(raw)}, "1 = 1")
        with pytest.raises(EventStoreError, match="payload did not round-trip"):
            OutboxPublisher._deserialize_sqlite(store.inner, (await rows(db))[0])
        assert (
            await OutboxPublisher(store, None, acknowledged_sink=sink).publish_pending()
            == 0
        )
        assert sink.received == []
        assert (await rows(db))[0]["status"] == "pending"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_explicit_custom_deserializer_preserves_event_type_and_identity():
    from pydantic import TypeAdapter

    from quadkit.serialization import loads

    class Serializer:
        def serialize(self, event):
            return event.__dict__

        def deserialize(self, event_type, data):
            assert event_type == "OrderApproved"
            return TypeAdapter(OrderApproved).validate_python(loads(data))

    db, store = await setup_stores(False, Serializer())
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={"ok": True})
    sink = Sink()
    try:
        await store.append("orders", [event])
        assert (
            await OutboxPublisher(store, acknowledged_sink=sink).publish_pending() == 1
        )
        assert sink.received == [event]
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_poison_event_does_not_block_other_event_within_same_batch():
    db, store = await setup_stores(False)
    store.register_event_type("OrderApproved", OrderApproved)
    first = OrderApproved(
        order_id=uuid4(), approved_on=date.today(), info={"fail": True}
    )
    second = OrderApproved(
        order_id=uuid4(), approved_on=date.today(), info={"fail": False}
    )

    class SelectiveSink(Sink):
        async def deliver(self, event):
            if event.info["fail"]:
                raise RuntimeError("unavailable")
            self.received.append(event)

    sink = SelectiveSink()
    try:
        await store.append("orders", [first, second])
        assert (
            await OutboxPublisher(store, acknowledged_sink=sink).publish_pending() == 1
        )
        states = {row["event_id"]: row["status"] for row in await rows(db)}
        assert states[str(first.event_id)] == "pending"
        assert states[str(second.event_id)] == "published"
        assert sink.received == [second]
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_other_task_cannot_relay_an_uncommitted_event(pooled):
    db, store = await setup_stores(pooled)
    store.register_event_type("OrderApproved", OrderApproved)
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    sink = Sink()
    relay = OutboxPublisher(store, acknowledged_sink=sink)
    start = asyncio.Event()
    entered = asyncio.Event()

    async def worker():
        await start.wait()
        entered.set()
        return await relay.publish_pending()

    task = asyncio.create_task(worker())
    try:
        with pytest.raises(ValueError, match="abort"):  # noqa: PT012
            async with db.transaction():
                await store.append("orders", [event])
                start.set()
                await entered.wait()
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(task), timeout=0.05)
                assert sink.received == []
                raise ValueError("abort")
        assert await asyncio.wait_for(task, timeout=2) == 0
        assert sink.received == []
        assert await rows(db) == []
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await db.disconnect()


@pytest.mark.asyncio
async def test_missing_provider_or_pool_capability_fails_closed(monkeypatch):
    from quadkit.sql.backends.sqlite import SQLiteConnectionPool
    from quadkit.sql.providers.sqlite_provider import SQLiteProvider

    db, store = await setup_stores(False)
    try:
        relay = OutboxPublisher(store, acknowledged_sink=Sink())
        monkeypatch.setattr(SQLiteProvider, "supports_outbox_committed_reads_v1", False)
        with pytest.raises(EventStoreError, match="verified SQL provider"):
            await relay.publish_pending()
    finally:
        await db.disconnect()
    monkeypatch.undo()
    db, store = await setup_stores(True)
    try:
        relay = OutboxPublisher(store, acknowledged_sink=Sink())
        monkeypatch.setattr(
            SQLiteConnectionPool, "supports_outbox_committed_reads_v1", False
        )
        with pytest.raises(EventStoreError, match="verified connection pool"):
            await relay.publish_pending()
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_custom_deserializer_cannot_return_string_event_identity():
    from quadkit.serialization import loads

    class Serializer:
        def serialize(self, event):
            return event.__dict__

        def deserialize(self, event_type, data):
            payload = loads(data)
            return OrderApproved(**payload)

    db, store = await setup_stores(False, Serializer())
    event = OrderApproved(order_id=uuid4(), approved_on=date.today(), info={})
    sink = Sink()
    try:
        await store.append("orders", [event])
        assert (
            await OutboxPublisher(store, acknowledged_sink=sink).publish_pending() == 0
        )
        assert sink.received == []
        assert (await rows(db))[0]["status"] == "pending"
    finally:
        await db.disconnect()
