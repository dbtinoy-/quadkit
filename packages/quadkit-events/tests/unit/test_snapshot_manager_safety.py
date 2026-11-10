"""Snapshot management must use stream versions and honor explicit retention."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.config import SqliteConfig
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.memory import InMemoryEventStore, InMemorySnapshotStore
from quadkit.events.stores.snapshot import EventCountPolicy, SnapshotManager
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.events.stores.sqlite.snapshot_store import SqliteSnapshotStore
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@dataclass(frozen=True, kw_only=True)
class Added(DomainEvent):
    amount: int


@pytest.mark.asyncio
@pytest.mark.parametrize("fully_compacted", [False, True])
async def test_force_snapshot_uses_absolute_memory_version(fully_compacted):
    aggregate_id = uuid4()
    events = InMemoryEventStore(max_events_per_stream=2)
    snapshots = InMemorySnapshotStore()
    manager = SnapshotManager(events, snapshots)
    await events.append(str(aggregate_id), [Added(amount=i) for i in (1, 2, 3)])
    if fully_compacted:
        await events.compact(str(aggregate_id), 3)
    snapshot = await manager.force_snapshot(
        aggregate_id, "Order", lambda: {"total": 6}, expected_version=3
    )
    assert snapshot.version == 3
    assert await manager.load_with_snapshot(aggregate_id, "Order") == (
        {"total": 6},
        [],
        3,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_force_snapshot_after_sqlite_compaction_and_reopen(tmp_path, pooled):
    path = str(tmp_path / "events.sqlite")
    pool = SQLiteConnectionPool(path) if pooled else None
    provider = SQLiteProvider(path, connection_pool=pool)
    await provider.connect()
    config = SqliteConfig(
        events_table="order_events", snapshots_table="order_snapshots"
    )
    events = SqliteEventStore(config=config, provider=provider)
    snapshots = SqliteSnapshotStore(config=config, provider=provider)
    await events.connect()
    await snapshots.connect()
    aggregate_id = uuid4()
    try:
        await events.append(str(aggregate_id), [Added(amount=i) for i in (1, 2, 3)])
        await events.compact(str(aggregate_id), 3)
        manager = SnapshotManager(events, snapshots)
        await manager.force_snapshot(
            aggregate_id, "Order", lambda: {"total": 6}, expected_version=3
        )
    finally:
        await provider.disconnect()
    pool = SQLiteConnectionPool(path) if pooled else None
    provider = SQLiteProvider(path, connection_pool=pool)
    await provider.connect()
    events = SqliteEventStore(config=config, provider=provider)
    snapshots = SqliteSnapshotStore(config=config, provider=provider)
    await events.connect()
    await snapshots.connect()
    try:
        state, replay, version = await SnapshotManager(
            events, snapshots
        ).load_with_snapshot(aggregate_id, "Order")
        assert (state, replay, version) == ({"total": 6}, [], 3)
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("versions", [[2, 3], [2, True], [2, -1], [2, None]])
async def test_force_snapshot_fails_closed_if_version_changes_or_invalid(versions):
    class VersionStore:
        async def get_stream_version(self, stream_id):
            return versions.pop(0)

    snapshots = InMemorySnapshotStore()
    manager = SnapshotManager(VersionStore(), snapshots)
    aggregate_id = uuid4()
    with pytest.raises(EventStoreError, match="version"):
        await manager.force_snapshot(aggregate_id, "Order", dict)
    assert await snapshots.get_latest(str(aggregate_id)) is None


@pytest.mark.asyncio
async def test_force_snapshot_requires_version_capability_and_checks_expected():
    snapshots = InMemorySnapshotStore()
    aggregate_id = uuid4()
    manager = SnapshotManager(object(), snapshots)
    with pytest.raises(EventStoreError, match="version"):
        await manager.force_snapshot(aggregate_id, "Order", dict)
    events = InMemoryEventStore()
    await events.append(str(aggregate_id), [Added(amount=1)])
    manager = SnapshotManager(events, snapshots)

    def must_not_extract():
        pytest.fail("stale expected version extracted state")

    with pytest.raises(EventStoreError, match="version"):
        await manager.force_snapshot(
            aggregate_id, "Order", must_not_extract, expected_version=0
        )
    assert await snapshots.get_latest(str(aggregate_id)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-1, True, 2.5])
async def test_invalid_retention_never_calls_store(bad):
    class Snapshots:
        async def delete_old_snapshots(self, *args):
            pytest.fail("invalid retention reached store")

    manager = SnapshotManager(InMemoryEventStore(), Snapshots())
    with pytest.raises(ValueError, match="keep_count"):
        await manager.cleanup_old_snapshots(uuid4(), bad)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "sqlite", "sqlite-pooled"])
async def test_cleanup_explicit_zero_deletes_only_requested_aggregate(
    tmp_path, backend
):
    db = None
    if backend == "memory":
        snapshots = InMemorySnapshotStore()
    else:
        path = str(tmp_path / "snapshots.sqlite")
        pool = SQLiteConnectionPool(path) if backend == "sqlite-pooled" else None
        db = SQLiteProvider(path, connection_pool=pool)
        await db.connect()
        snapshots = SqliteSnapshotStore(provider=db)
        await snapshots.connect()
    manager = SnapshotManager(InMemoryEventStore(), snapshots)
    a, b = uuid4(), uuid4()
    try:
        await manager.create_snapshot(a, "Order", 1, {})
        await manager.create_snapshot(a, "Order", 2, {})
        await manager.create_snapshot(b, "Order", 1, {})
        assert await manager.cleanup_old_snapshots(a, keep_count=0) == 2
        assert await snapshots.get_latest(str(a)) is None
        assert (await snapshots.get_latest(str(b))).version == 1
    finally:
        if db is not None:
            await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("ack", [None, True, 0, 2])
async def test_save_does_not_snapshot_on_invalid_append_acknowledgement(ack):
    class EventStore:
        async def append(self, *args):
            return ack

    snapshots = InMemorySnapshotStore()
    manager = SnapshotManager(EventStore(), snapshots, policy=EventCountPolicy(1))
    aggregate_id = uuid4()
    with pytest.raises(EventStoreError, match="version"):
        await manager.save_and_maybe_snapshot(
            aggregate_id, "Order", [Added(amount=1)], {}, 0
        )
    assert await snapshots.get_latest(str(aggregate_id)) is None
    assert str(aggregate_id) not in manager._events_since_snapshot


@pytest.mark.asyncio
async def test_repository_force_snapshot_rejects_pending_and_stale_aggregate():
    from quadkit.events.aggregates import AggregateRoot
    from quadkit.events.repository import EventSourcingRepository

    class Account(AggregateRoot):
        total: int = 0

        def _handle_added(self, event):
            self.total += event.amount

        def add(self, amount):
            self._apply(Added(aggregate_id=self.id, amount=amount))

    events, snapshots = InMemoryEventStore(), InMemorySnapshotStore()
    repository = EventSourcingRepository(Account, events, snapshots)
    account = Account()
    account.add(1)
    with pytest.raises(EventStoreError, match="pending"):
        await repository.force_snapshot(account)
    assert await snapshots.get_latest(str(account.id)) is None
    await repository.save(account)
    stale = await repository.get(account.id)
    await events.append(
        str(account.id), [Added(aggregate_id=account.id, amount=2)], expected_version=1
    )
    with pytest.raises(EventStoreError, match="version"):
        await repository.force_snapshot(stale)
    assert await snapshots.get_latest(str(account.id)) is None
    latest = await repository.get(account.id)
    await repository.force_snapshot(latest)
    snap = await snapshots.get_latest(str(account.id))
    assert (snap.version, snap.state["total"]) == (2, 3)


@pytest.mark.asyncio
async def test_outbox_delegates_version_for_snapshot_after_compaction():
    from quadkit.events.stores.outbox import OutboxEventStore

    events = InMemoryEventStore()
    aggregate_id = uuid4()
    await events.append(str(aggregate_id), [Added(amount=1)])
    await events.compact(str(aggregate_id), 1)
    snapshots = InMemorySnapshotStore()
    manager = SnapshotManager(OutboxEventStore(events), snapshots)
    snapshot = await manager.force_snapshot(
        aggregate_id, "Order", lambda: {"total": 1}, expected_version=1
    )
    assert snapshot.version == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_sqlite_outbox_wrapper_snapshot_after_full_compaction(tmp_path, pooled):
    from quadkit.events.stores.outbox import OutboxEventStore

    path = str(tmp_path / "outbox.sqlite")
    pool = SQLiteConnectionPool(path) if pooled else None
    provider = SQLiteProvider(path, connection_pool=pool)
    await provider.connect()
    events = SqliteEventStore(provider=provider)
    snapshots = SqliteSnapshotStore(provider=provider)
    await events.connect()
    await snapshots.connect()
    aggregate_id = uuid4()
    try:
        await events.append(str(aggregate_id), [Added(amount=1)])
        await events.compact(str(aggregate_id), 1)
        manager = SnapshotManager(OutboxEventStore(events), snapshots)
        snapshot = await manager.force_snapshot(
            aggregate_id, "Order", lambda: {"total": 1}, expected_version=1
        )
        assert snapshot.version == 1
        assert await manager.load_with_snapshot(aggregate_id, "Order") == (
            {"total": 1},
            [],
            1,
        )
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-1, True, 1.5])
async def test_invalid_expected_snapshot_version_fails_before_extraction(bad):
    manager = SnapshotManager(InMemoryEventStore(), InMemorySnapshotStore())

    def extract():
        pytest.fail("invalid expected version extracted state")

    with pytest.raises(ValueError, match="expected_version"):
        await manager.force_snapshot(uuid4(), "Order", extract, expected_version=bad)


@pytest.mark.asyncio
async def test_bad_append_ack_does_not_imply_the_append_was_rolled_back():
    actual = InMemoryEventStore()

    class UncertainAcknowledgement:
        async def append(self, *args):
            await actual.append(*args)

    snapshots = InMemorySnapshotStore()
    manager = SnapshotManager(
        UncertainAcknowledgement(), snapshots, EventCountPolicy(1)
    )
    aggregate_id = uuid4()
    with pytest.raises(EventStoreError, match="version"):
        await manager.save_and_maybe_snapshot(
            aggregate_id, "Order", [Added(amount=1)], {"total": 1}, 0
        )
    assert await actual.get_stream_version(str(aggregate_id)) == 1
    assert await snapshots.get_latest(str(aggregate_id)) is None
