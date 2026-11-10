"""Aggregate replay rejects detectable incomplete or changing histories."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.aggregates import AggregateRoot
from quadkit.events.exceptions import EventStoreError
from quadkit.events.repository import EventSourcingRepository
from quadkit.events.stores.memory import InMemoryEventStore, InMemorySnapshotStore
from quadkit.events.stores.snapshot import SnapshotManager
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.events.stores.sqlite.snapshot_store import SqliteSnapshotStore
from quadkit.events.types import Snapshot
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@dataclass(frozen=True, kw_only=True)
class Added(DomainEvent):
    amount: int


class Account(AggregateRoot):
    total: int = 0

    def _handle_added(self, event):
        self.total += event.amount


async def seed(events, snapshots, aggregate_id, snapshot_version=1):
    await events.append(
        str(aggregate_id),
        [Added(aggregate_id=aggregate_id, amount=i) for i in (1, 2, 3)],
    )
    await snapshots.save_snapshot(
        Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type="Account",
            version=snapshot_version,
            state={"total": 1},
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("with_snapshot", [False, True])
@pytest.mark.parametrize("truncation", ["empty", "drop_first", "drop_last"])
async def test_repository_rejects_truncated_history(with_snapshot, truncation):
    class TruncatedMemory(InMemoryEventStore):
        async def read(self, *args, **kwargs):
            events = await super().read(*args, **kwargs)
            if truncation == "empty":
                return []
            return events[1:] if truncation == "drop_first" else events[:-1]

    events, snapshots, aggregate_id = (
        TruncatedMemory(),
        InMemorySnapshotStore(),
        uuid4(),
    )
    await seed(events, snapshots, aggregate_id)
    repo = EventSourcingRepository(
        Account, events, snapshots if with_snapshot else None
    )
    with pytest.raises(EventStoreError, match="history"):
        await repo.get(aggregate_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "sqlite", "sqlite-pooled"])
async def test_snapshot_ahead_of_stream_is_rejected_after_reopen(tmp_path, backend):
    db = None
    if backend == "memory":
        events, snapshots = InMemoryEventStore(), InMemorySnapshotStore()
    else:
        path = str(tmp_path / "future.sqlite")
        pool = SQLiteConnectionPool(path) if backend == "sqlite-pooled" else None
        db = SQLiteProvider(path, connection_pool=pool)
        await db.connect()
        events = SqliteEventStore(provider=db)
        snapshots = SqliteSnapshotStore(provider=db)
        await events.connect()
        await snapshots.connect()
    aggregate_id = uuid4()
    try:
        await seed(events, snapshots, aggregate_id, snapshot_version=4)
        if db is not None:
            await db.disconnect()
            pool = SQLiteConnectionPool(path) if backend == "sqlite-pooled" else None
            db = SQLiteProvider(path, connection_pool=pool)
            await db.connect()
            events, snapshots = (
                SqliteEventStore(provider=db),
                SqliteSnapshotStore(provider=db),
            )
            await events.connect()
            await snapshots.connect()
        with pytest.raises(EventStoreError, match="version"):
            await EventSourcingRepository(Account, events, snapshots).get(aggregate_id)
    finally:
        if db is not None:
            await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("with_snapshot", [False, True])
async def test_version_change_during_replay_fails_closed(with_snapshot):
    class ChangingStore(InMemoryEventStore):
        async def read(self, stream_id, *args, **kwargs):
            result = await super().read(stream_id, *args, **kwargs)
            await self.append(stream_id, [Added(amount=10)])
            return result

    events, snapshots, aggregate_id = ChangingStore(), InMemorySnapshotStore(), uuid4()
    await seed(events, snapshots, aggregate_id)
    repository = EventSourcingRepository(
        Account, events, snapshots if with_snapshot else None
    )
    with pytest.raises(EventStoreError, match="version"):
        await repository.get(aggregate_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [True, -1, None, "3"])
async def test_invalid_version_does_not_advance_snapshot_tracking(bad):
    class InvalidVersion(InMemoryEventStore):
        async def get_stream_version(self, stream_id):
            return bad

    events, snapshots, aggregate_id = InvalidVersion(), InMemorySnapshotStore(), uuid4()
    await seed(events, snapshots, aggregate_id)
    manager = SnapshotManager(events, snapshots)
    manager._events_since_snapshot[str(aggregate_id)] = 9
    with pytest.raises(EventStoreError, match="version"):
        await manager.load_with_snapshot(aggregate_id, "Account")
    assert manager._events_since_snapshot[str(aggregate_id)] == 9


@pytest.mark.asyncio
@pytest.mark.parametrize("with_snapshot", [False, True])
async def test_missing_version_capability_does_not_return_partial_aggregate(
    with_snapshot,
):
    class MinimalStore:
        async def read(self, stream_id, from_version=0, to_version=None, limit=None):
            return []

    snapshots, aggregate_id = InMemorySnapshotStore(), uuid4()
    if with_snapshot:
        await snapshots.save_snapshot(
            Snapshot(
                aggregate_id=aggregate_id, aggregate_type="Account", version=1, state={}
            )
        )
    repo = EventSourcingRepository(
        Account, MinimalStore(), snapshots if with_snapshot else None
    )
    with pytest.raises(EventStoreError, match="version"):
        await repo.get(aggregate_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
@pytest.mark.parametrize("with_snapshot", [False, True])
async def test_sqlite_truncated_read_is_rejected(tmp_path, pooled, with_snapshot):
    class TruncatedSqlite(SqliteEventStore):
        async def read(self, *args, **kwargs):
            result = await super().read(*args, **kwargs)
            return result[:-1]

    path = str(tmp_path / "truncated.sqlite")
    pool = SQLiteConnectionPool(path) if pooled else None
    db = SQLiteProvider(path, connection_pool=pool)
    await db.connect()
    events, snapshots = TruncatedSqlite(provider=db), SqliteSnapshotStore(provider=db)
    await events.connect()
    await snapshots.connect()
    events.register_event_type("Added", Added)
    aggregate_id = uuid4()
    try:
        await seed(events, snapshots, aggregate_id)
        with pytest.raises(EventStoreError, match="history"):
            await EventSourcingRepository(
                Account, events, snapshots if with_snapshot else None
            ).get(aggregate_id)
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_snapshot_version_zero_and_empty_stream_are_distinct():
    events, snapshots, aggregate_id = (
        InMemoryEventStore(),
        InMemorySnapshotStore(),
        uuid4(),
    )
    repository = EventSourcingRepository(Account, events, snapshots)
    assert await repository.get(aggregate_id) is None
    await snapshots.save_snapshot(
        Snapshot(
            aggregate_id=aggregate_id, aggregate_type="Account", version=0, state={}
        )
    )
    loaded = await repository.get(aggregate_id)
    assert loaded.id == aggregate_id
    assert loaded.version == 0


@pytest.mark.asyncio
async def test_sync_version_capability_fails_closed():
    class SynchronousVersion:
        def get_stream_version(self, stream_id):
            return 0

        async def read(self, *args, **kwargs):
            pytest.fail("invalid version capability reached read")

    with pytest.raises(EventStoreError, match="awaitable"):
        await EventSourcingRepository(Account, SynchronousVersion()).get(uuid4())


@pytest.mark.asyncio
async def test_invalid_second_version_preserves_manager_tracking():
    class InvalidSecondVersion(InMemoryEventStore):
        calls = 0

        async def get_stream_version(self, stream_id):
            self.calls += 1
            if self.calls == 2:
                return None
            return await super().get_stream_version(stream_id)

    events, snapshots, aggregate_id = (
        InvalidSecondVersion(),
        InMemorySnapshotStore(),
        uuid4(),
    )
    await seed(events, snapshots, aggregate_id)
    manager = SnapshotManager(events, snapshots)
    manager._events_since_snapshot[str(aggregate_id)] = 7
    with pytest.raises(EventStoreError, match="version"):
        await manager.load_with_snapshot(aggregate_id, "Account")
    assert manager._events_since_snapshot[str(aggregate_id)] == 7
