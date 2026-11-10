"""SQLite event payloads retain their typed identity and declared data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.exceptions import EventStoreError
from quadkit.events.messages.event import Event
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.serialization import dumps_str, loads
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@dataclass(frozen=True, kw_only=True)
class Line:
    item_id: UUID
    price: Decimal
    when: date


@dataclass(frozen=True, kw_only=True)
class Approved(DomainEvent):
    order_id: UUID
    lines: list[Line]
    completed_at: datetime


@dataclass(frozen=True, kw_only=True)
class EventChild(Event):
    related_id: UUID


class LegacyEvent(Event):
    pass


async def open_store(path, pooled):
    pool = SQLiteConnectionPool(str(path)) if pooled else None
    provider = SQLiteProvider(str(path), connection_pool=pool)
    await provider.connect()
    store = SqliteEventStore(provider=provider)
    await store.connect()
    for cls in (Approved, EventChild, LegacyEvent):
        store.register_event_type(cls.__name__, cls)
    return provider, store


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_registered_typed_payloads_round_trip_across_reopen(tmp_path, pooled):
    path = tmp_path / "typed.sqlite"
    db, store = await open_store(path, pooled)
    approved = Approved(
        aggregate_id=uuid4(),
        order_id=uuid4(),
        completed_at=datetime(2024, 4, 1, 12, 5, tzinfo=UTC),
        lines=[Line(item_id=uuid4(), price=Decimal("1.25"), when=date(2024, 2, 3))],
    )
    child = EventChild(related_id=uuid4(), causation_id=uuid4(), correlation_id=uuid4())
    try:
        await store.append("orders", [approved, child])
    finally:
        await db.disconnect()
    db, store = await open_store(path, pooled)
    try:
        read = await store.read("orders")
        assert read == [approved, child]
        assert isinstance(read[0].event_id, UUID)
        assert isinstance(read[0].aggregate_id, UUID)
        assert isinstance(read[0].occurred_at, datetime)
        assert isinstance(read[0].order_id, UUID)
        assert isinstance(read[0].lines[0], Line)
        assert isinstance(read[0].lines[0].price, Decimal)
        assert isinstance(read[0].lines[0].when, date)
        assert isinstance(read[1].causation_id, UUID)
        assert isinstance(read[1].correlation_id, UUID)
        all_events = [e async for e in store.stream_all()]
        assert all_events[0] == approved.__class__(
            **{**approved.__dict__, "sequence_number": 1}
        )
        assert (await store.find_by_type("Approved"))[0] == approved
        typed_events = [e async for e in store.stream_by_type(["Approved"])]
        assert typed_events[0].order_id == approved.order_id
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_legacy_event_retains_dynamic_fields_and_base_types(tmp_path):
    db, store = await open_store(tmp_path / "legacy.sqlite", False)
    original = LegacyEvent(
        label="keep me",
        causation_id=uuid4(),
        correlation_id=uuid4(),
        aggregate_id=uuid4(),
    )
    try:
        await store.append("s", [original])
        result = (await store.read("s"))[0]
        assert type(result) is LegacyEvent
        assert result.label == "keep me"
        assert result.event_id == original.event_id
        assert result.aggregate_id == original.aggregate_id
        assert result.occurred_at == original.occurred_at
        assert result.causation_id == original.causation_id
        assert result.correlation_id == original.correlation_id
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_unregistered_fallback_restores_base_identity_and_time(tmp_path):
    db, store = await open_store(tmp_path / "fallback.sqlite", False)
    original = LegacyEvent(label="x", aggregate_id=uuid4())
    try:
        await store.append("s", [original])
        store.serializer._event_type_registry.clear()
        result = (await store.read("s"))[0]
        assert type(result) is DomainEvent
        assert result.event_id == original.event_id
        assert result.aggregate_id == original.aggregate_id
        assert result.occurred_at == original.occurred_at
        assert result.label == "x"
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["bad_uuid", "unknown_top_level", "unknown_nested", "lossy_number"]
)
async def test_declared_payload_corruption_does_not_silently_lose_data(tmp_path, kind):
    db, store = await open_store(tmp_path / "bad.sqlite", False)
    event = Approved(
        order_id=uuid4(),
        completed_at=datetime.now(UTC),
        lines=[Line(item_id=uuid4(), price=Decimal("1.25"), when=date.today())],
    )
    try:
        await store.append("s", [event])
        row = (await db.execute_query("SELECT event_data FROM events")).rows[0]
        payload = loads(row["event_data"])
        if kind == "bad_uuid":
            payload["order_id"] = "not-a-uuid"
        elif kind == "unknown_top_level":
            payload["extra"] = "do-not-drop"
        elif kind == "unknown_nested":
            payload["lines"][0]["extra"] = "do-not-drop"
        else:
            payload["lines"][0]["price"] = 1.25
        await db.execute("UPDATE events SET event_data = ?", [dumps_str(payload)])
        with pytest.raises(EventStoreError, match="SQLite event payload"):
            await store.read("s")
    finally:
        await db.disconnect()


@dataclass(frozen=True, slots=True, kw_only=True)
class Slotted(DomainEvent):
    order_id: UUID


@pytest.mark.asyncio
async def test_slotted_dataclass_fields_are_persisted_and_restored(tmp_path):
    db, store = await open_store(tmp_path / "slots.sqlite", False)
    store.register_event_type("Slotted", Slotted)
    event = Slotted(order_id=uuid4())
    try:
        await store.append("s", [event])
        assert (await store.read("s"))[0] == event
        assert (await store.find_by_type("Slotted"))[0].order_id == event.order_id
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_older_payload_may_gain_declared_defaults_on_restore(tmp_path):
    db, store = await open_store(tmp_path / "defaults.sqlite", False)
    original = Approved(order_id=uuid4(), completed_at=datetime.now(UTC), lines=[])
    try:
        await store.append("s", [original])
        payload = loads(
            (await db.execute_query("SELECT event_data FROM events")).rows[0][
                "event_data"
            ]
        )
        del payload["schema_version"]
        await db.execute("UPDATE events SET event_data = ?", [dumps_str(payload)])
        result = (await store.read("s"))[0]
        assert result.schema_version == 1
        assert result.event_id == original.event_id
        assert result.order_id == original.order_id
    finally:
        await db.disconnect()
