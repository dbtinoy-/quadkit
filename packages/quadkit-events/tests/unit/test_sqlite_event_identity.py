"""SQLite event IDs must agree with built-in DomainEvent payloads."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.outbox import OutboxEventStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.serialization import dumps_str, loads
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@dataclass(frozen=True, kw_only=True)
class Added(DomainEvent):
    amount: int


class Legacy(DomainEvent):
    pass


async def open_store(path, pooled):
    pool = SQLiteConnectionPool(str(path)) if pooled else None
    db = SQLiteProvider(str(path), connection_pool=pool)
    await db.connect()
    store = SqliteEventStore(provider=db)
    await store.connect()
    store.register_event_type("Added", Added)
    store.register_event_type("Legacy", Legacy)
    return db, store


async def consume(store, method, event_type):
    if method == "read":
        return await store.read("s")
    if method == "find":
        return await store.find_by_type(event_type)
    if method == "stream_all":
        return [event async for event in store.stream_all()]
    return [event async for event in store.stream_by_type([event_type])]


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
@pytest.mark.parametrize("kind", ["payload_mismatch", "payload_invalid", "row_invalid"])
@pytest.mark.parametrize("method", ["read", "find", "stream_all", "stream_by_type"])
@pytest.mark.parametrize("mode", ["registered", "fallback", "legacy"])
async def test_inconsistent_event_identity_fails_closed(
    tmp_path, pooled, kind, method, mode
):
    path = tmp_path / "bad-id.sqlite"
    db, store = await open_store(path, pooled)
    event = Legacy(value=1) if mode == "legacy" else Added(amount=1)
    try:
        await store.append("s", [event])
        payload = loads(
            (await db.execute_query("SELECT event_data FROM events")).rows[0][
                "event_data"
            ]
        )
        if kind == "row_invalid":
            await db.execute("UPDATE events SET event_id = ?", ["invalid-row-id"])
        else:
            payload["event_id"] = (
                str(uuid4()) if kind == "payload_mismatch" else "invalid-payload-id"
            )
            await db.execute("UPDATE events SET event_data = ?", [dumps_str(payload)])
    finally:
        await db.disconnect()
    db, store = await open_store(path, pooled)
    if mode == "fallback":
        store.serializer._event_type_registry.clear()
    try:
        with pytest.raises(EventStoreError, match="identity"):
            await consume(store, method, type(event).__name__)
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["registered", "fallback", "legacy"])
async def test_missing_payload_identity_uses_persisted_row_identity(tmp_path, mode):
    db, store = await open_store(tmp_path / "old.sqlite", False)
    event = Legacy(value=1) if mode == "legacy" else Added(amount=1)
    try:
        await store.append("s", [event])
        payload = loads(
            (await db.execute_query("SELECT event_data FROM events")).rows[0][
                "event_data"
            ]
        )
        del payload["event_id"]
        await db.execute("UPDATE events SET event_data = ?", [dumps_str(payload)])
        if mode == "fallback":
            store.serializer._event_type_registry.clear()
        for method in ("read", "find", "stream_all", "stream_by_type"):
            restored = (await consume(store, method, type(event).__name__))[0]
            assert restored.event_id == event.event_id
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("outbox", [False, True])
@pytest.mark.parametrize("pooled", [False, True])
async def test_conflicting_input_identity_rolls_back_whole_batch(
    tmp_path, outbox, pooled
):
    db, store = await open_store(tmp_path / "append.sqlite", pooled)
    try:
        await db.execute_query(
            "CREATE TABLE event_outbox (event_id TEXT PRIMARY KEY, event_type TEXT, event_data TEXT, metadata TEXT, timestamp TEXT, status TEXT, published_at TEXT)"
        )
        first = Added(amount=1)
        # Plain legacy events allow an additional id distinct from event_id.
        bad = Legacy(id=uuid4(), value=2)
        writer = OutboxEventStore(store) if outbox else store
        with pytest.raises(EventStoreError, match="identity"):
            await writer.append("s", [first, bad], expected_version=0)
        assert (await db.execute_query("SELECT * FROM events")).rows == []
        assert (await db.execute_query("SELECT * FROM event_outbox")).rows == []
        assert await store.get_stream_version("s") == 0
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("corruption", ["different", "string"])
async def test_legacy_constructor_cannot_change_restored_identity(tmp_path, corruption):
    class ChangingIdentity(DomainEvent):
        alter = False

        def __post_init__(self):
            super().__post_init__()
            if self.alter:
                altered = uuid4() if corruption == "different" else str(self.event_id)
                object.__setattr__(self, "event_id", altered)

    db, store = await open_store(tmp_path / "changed-id.sqlite", False)
    store.register_event_type("ChangingIdentity", ChangingIdentity)
    try:
        await store.append("s", [ChangingIdentity()])
        ChangingIdentity.alter = True
        with pytest.raises(EventStoreError, match="identity"):
            await store.read("s")
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_registered_non_domain_payload_retains_its_custom_identity_contract(
    tmp_path,
):
    class CustomEvent:
        def __init__(self, id, value):
            self.id = id
            self.value = value

    db, store = await open_store(tmp_path / "custom.sqlite", False)
    store.register_event_type("CustomEvent", CustomEvent)
    try:
        await store.append("s", [CustomEvent(id="not-a-uuid", value=5)])
        restored = (await store.read("s"))[0]
        assert (restored.id, restored.value) == ("not-a-uuid", 5)
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_matching_legacy_id_alias_is_accepted(tmp_path):
    db, store = await open_store(tmp_path / "alias.sqlite", False)
    event_id = uuid4()
    event = Legacy(id=event_id, event_id=event_id, value=1)
    try:
        await store.append("s", [event])
        restored = (await store.read("s"))[0]
        assert restored.event_id == event_id
        assert str(restored.id) == str(event_id)
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_explicit_domain_event_type_remains_independent_of_sqlite_class_key(
    tmp_path,
):
    db, store = await open_store(tmp_path / "type-alias.sqlite", False)
    event = Added(amount=1, event_type="business.added")
    try:
        await store.append("s", [event])
        row = (await db.execute_query("SELECT event_type FROM events")).rows[0]
        assert row["event_type"] == "Added"
        assert (await store.read("s"))[0].event_type == "business.added"
    finally:
        await db.disconnect()
