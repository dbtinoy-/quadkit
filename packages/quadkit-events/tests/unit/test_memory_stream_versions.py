"""In-memory stream high-water marks survive retention and compaction."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.aggregates import AggregateRoot
from quadkit.events.exceptions import ConcurrencyError, EventStoreError
from quadkit.events.repository import EventSourcingRepository
from quadkit.events.stores.memory import InMemoryEventStore, InMemorySnapshotStore
from quadkit.events.types import Snapshot


@dataclass(frozen=True, kw_only=True)
class Added(DomainEvent):
    amount: int


class Account(AggregateRoot):
    total: int = 0

    def _handle_added(self, event):
        self.total += event.amount


@pytest.mark.asyncio
async def test_retention_preserves_high_water_and_absolute_reads():
    store = InMemoryEventStore(max_events_per_stream=2)
    assert (
        await store.append(
            "s", [Added(amount=i) for i in (1, 2, 3)], expected_version=0
        )
        == 3
    )
    assert await store.get_stream_version("s") == 3
    assert await store.append("s", []) == 3
    with pytest.raises(EventStoreError, match="history"):
        await store.read("s")
    with pytest.raises(EventStoreError, match="history"):
        await store.read("s", from_version=1, to_version=1)
    assert [e.amount for e in await store.read("s", from_version=2)] == [2, 3]
    assert [e.amount for e in await store.read("s", from_version=3, to_version=3)] == [
        3
    ]
    with pytest.raises(ConcurrencyError):
        await store.append("s", [Added(amount=4)], expected_version=2)
    assert await store.append("s", [Added(amount=4)], expected_version=3) == 4
    assert await store.get_stream_version("s") == 4
    assert [e.amount for e in await store.read("s", from_version=3)] == [3, 4]
    assert await store.read("s", from_version=5) == []
    assert await store.read("s", from_version=4, to_version=3) == []
    assert await store.read("s", limit=0) == []
    assert [e.sequence_number async for e in store.stream_all()] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_compaction_preserves_version_and_rejects_missing_prefix():
    store = InMemoryEventStore(max_events_per_stream=0)
    await store.append("s", [Added(amount=i) for i in (1, 2, 3)])
    assert await store.compact("s", up_to_version=2) == 2
    assert await store.get_stream_version("s") == 3
    with pytest.raises(EventStoreError, match="history"):
        await store.read("s", from_version=2)
    assert [e.amount for e in await store.read("s", from_version=3)] == [3]
    assert await store.compact("s", up_to_version=2) == 0
    assert await store.compact("s", up_to_version=3) == 1
    assert await store.get_stream_version("s") == 3
    with pytest.raises(EventStoreError, match="history"):
        await store.read("s")
    assert await store.read("s", from_version=4) == []
    with pytest.raises(ConcurrencyError):
        await store.append("s", [Added(amount=4)], expected_version=0)
    assert await store.append("s", [Added(amount=4)], expected_version=3) == 4
    assert [e.amount for e in await store.read("s", from_version=4)] == [4]
    assert await store.compact("s", up_to_version=4) == 1
    assert await store.get_stream_version("s") == 4


@pytest.mark.asyncio
async def test_retention_and_compaction_are_independent_per_stream():
    store = InMemoryEventStore(max_events_per_stream=2)
    assert (
        await store.append("a", [Added(amount=1), Added(amount=2), Added(amount=3)])
        == 3
    )
    assert await store.append("b", [Added(amount=10)]) == 1
    assert await store.compact("a", up_to_version=2) == 1
    assert await store.get_stream_version("a") == 3
    assert await store.get_stream_version("b") == 1
    assert [e.amount for e in await store.read("a", from_version=3)] == [3]
    assert [e.amount for e in await store.read("b")] == [10]
    store.clear()
    assert await store.get_stream_version("a") == 0
    assert await store.read("a") == []
    assert await store.append("a", [Added(amount=4)], expected_version=0) == 1


@pytest.mark.asyncio
async def test_repository_never_replays_missing_retained_prefix():
    store, snapshots = (
        InMemoryEventStore(max_events_per_stream=2),
        InMemorySnapshotStore(),
    )
    aggregate_id = uuid4()
    await store.append(
        str(aggregate_id),
        [Added(aggregate_id=aggregate_id, amount=i) for i in (1, 2, 3)],
    )
    with pytest.raises(EventStoreError, match="history"):
        await EventSourcingRepository(Account, store).get(aggregate_id)
    await snapshots.save_snapshot(
        Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type="Account",
            version=1,
            state={"total": 1},
        )
    )
    repo = EventSourcingRepository(Account, store, snapshots)
    loaded = await repo.get(aggregate_id)
    assert loaded.total == 6
    assert loaded.version == 3
    await store.append(
        str(aggregate_id),
        [Added(aggregate_id=aggregate_id, amount=4)],
        expected_version=3,
    )
    with pytest.raises(EventStoreError, match="history"):
        await repo.get(aggregate_id)


@pytest.mark.asyncio
async def test_batch_failure_after_eviction_does_not_change_high_water():
    from quadkit.events.messages.event import Event

    class Broken(Event):
        def __copy__(self):
            raise RuntimeError("copy failure")

    store = InMemoryEventStore(max_events_per_stream=2)
    await store.append("s", [Event(), Event(), Event()], expected_version=0)
    with pytest.raises(EventStoreError, match="prepare"):
        await store.append("s", [Event(), Broken()], expected_version=3)
    assert await store.get_stream_version("s") == 3
    assert store.get_global_position() == 3
    assert [e.version for e in await store.read("s", from_version=2)] == [2, 3]
    assert await store.append("s", [Event()], expected_version=3) == 4
    assert [e.version for e in await store.read("s", from_version=3)] == [3, 4]
