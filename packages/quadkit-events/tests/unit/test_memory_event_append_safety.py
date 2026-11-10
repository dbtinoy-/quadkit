"""In-memory appends support declared dataclasses and commit complete batches."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.exceptions import ConcurrencyError, EventStoreError
from quadkit.events.messages.event import Event
from quadkit.events.stores.memory import InMemoryEventStore


@dataclass(frozen=True, kw_only=True)
class Added(DomainEvent):
    amount: int


@dataclass(frozen=True, slots=True, kw_only=True)
class Slotted(Event):
    note: str


class Legacy(Event):
    pass


@dataclass(frozen=True, kw_only=True)
class BadCopy(DomainEvent):
    def __copy__(self):
        raise ValueError("private copy error")


@dataclass(frozen=True, kw_only=True)
class SharedCopy(DomainEvent):
    def __copy__(self):
        return self


@pytest.mark.asyncio
async def test_dataclasses_slots_and_legacy_keep_payload_and_originals():
    store = InMemoryEventStore()
    aggregate_id = uuid4()
    first = Added(aggregate_id=aggregate_id, amount=7)
    second = Slotted(aggregate_id=aggregate_id, note="typed")
    third = Legacy(aggregate_id=aggregate_id, dynamic="preserve", version=9)
    assert await store.append("orders", [first, second, third], expected_version=0) == 3
    saved = await store.read("orders")
    assert [type(event) for event in saved] == [Added, Slotted, Legacy]
    assert saved[0].amount == 7
    assert saved[1].note == "typed"
    assert saved[1].version == 2
    assert saved[2].dynamic == "preserve"
    assert saved[2].version == 3
    assert [event.sequence_number for event in saved] == [1, 2, 3]
    assert all(event.stream_id == "orders" for event in saved)
    assert all(
        original is not stored
        for original, stored in zip([first, second, third], saved, strict=True)
    )
    assert first.sequence_number is None
    assert second.sequence_number is None
    assert third.sequence_number is None
    assert third.version == 9
    assert not hasattr(first, "stream_id")
    assert [
        event.sequence_number
        async for event in store.stream_by_type(["Added", "Slotted", "Legacy"])
    ] == [1, 2, 3]
    part = int(md5(b"orders", usedforsecurity=False).hexdigest()[:8], 16) % 3
    assert [
        event.sequence_number
        async for event in store.stream_all(partition=part, total_partitions=3)
    ] == [1, 2, 3]
    assert [
        event
        async for event in store.stream_all(
            partition=(part + 1) % 3, total_partitions=3
        )
    ] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [BadCopy(), SharedCopy()])
async def test_copy_failure_on_later_event_leaves_entire_batch_uncommitted(bad):
    store = InMemoryEventStore()
    good = Added(amount=1)
    with pytest.raises(EventStoreError, match="in-memory event") as error:
        await store.append("orders", [good, bad], expected_version=0)
    assert "private copy error" not in str(error.value)
    assert await store.read("orders") == []
    assert await store.get_stream_version("orders") == 0
    assert await store.get_stream_ids() == []
    assert store.get_global_position() == 0
    assert [event async for event in store.stream_all()] == []
    assert [event async for event in store.stream_by_type(["Added"])] == []
    assert good.sequence_number is None
    assert await store.append("orders", [good], expected_version=0) == 1
    assert (await store.read("orders"))[0].sequence_number == 1


@pytest.mark.asyncio
async def test_failed_append_preserves_existing_stream_and_other_indexes():
    store = InMemoryEventStore()
    await store.append("other", [Added(amount=8)])
    await store.append("orders", [Legacy(dynamic="existing")])
    with pytest.raises(EventStoreError, match="in-memory event"):
        await store.append("orders", [Added(amount=2), BadCopy()], expected_version=1)
    assert await store.get_stream_version("orders") == 1
    assert store.get_global_position() == 2
    assert [e.sequence_number async for e in store.stream_all()] == [1, 2]
    assert [e.sequence_number async for e in store.stream_by_type(["Added"])] == [1]
    assert await store.append("orders", [Added(amount=3)], expected_version=1) == 2
    assert [e.sequence_number async for e in store.stream_all()] == [1, 2, 3]
    assert [e.sequence_number async for e in store.stream_by_type(["Added"])] == [1, 3]


@pytest.mark.asyncio
async def test_concurrency_conflict_never_stages_events():
    store = InMemoryEventStore()
    await store.append("orders", [Legacy(dynamic="existing")])
    with pytest.raises(ConcurrencyError):
        await store.append("orders", [BadCopy()], expected_version=0)
    assert store.get_global_position() == 1
    assert await store.get_stream_version("orders") == 1


@pytest.mark.asyncio
async def test_declared_dataclass_replays_through_repository_with_snapshot():
    from quadkit.events.aggregates import AggregateRoot
    from quadkit.events.repository import EventSourcingRepository
    from quadkit.events.stores.memory import InMemorySnapshotStore
    from quadkit.events.types import Snapshot

    class Account(AggregateRoot):
        total: int = 0

        def _handle_added(self, event):
            self.total += event.amount

    store, snapshots = InMemoryEventStore(), InMemorySnapshotStore()
    aggregate_id = uuid4()
    await store.append(str(aggregate_id), [Added(aggregate_id=aggregate_id, amount=1)])
    await snapshots.save_snapshot(
        Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type="Account",
            version=1,
            state={"total": 1},
        )
    )
    await store.append(str(aggregate_id), [Added(aggregate_id=aggregate_id, amount=2)])
    loaded = await EventSourcingRepository(Account, store, snapshots).get(aggregate_id)
    assert loaded.id == aggregate_id
    assert loaded.version == 2
    assert loaded.total == 3
