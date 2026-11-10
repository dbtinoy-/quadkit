"""Existence and stream information reflect compaction high-water marks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.aggregates import AggregateRoot
from quadkit.events.exceptions import EventStoreError
from quadkit.events.repository import EventSourcingRepository
from quadkit.events.stores.memory import InMemoryEventStore, InMemorySnapshotStore
from quadkit.events.stores.outbox import OutboxEventStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.events.stores.streaming import StreamingEventStore
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


async def open_store(tmp_path, backend):
    if backend == "memory":
        return None, InMemoryEventStore(max_events_per_stream=0)
    path = str(tmp_path / "streams.sqlite")
    pool = SQLiteConnectionPool(path) if backend == "sqlite-pooled" else None
    db = SQLiteProvider(path, connection_pool=pool)
    await db.connect()
    store = SqliteEventStore(provider=db)
    await store.connect()
    store.register_event_type("Added", Added)
    return db, store


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "sqlite", "sqlite-pooled"])
@pytest.mark.parametrize("wrapper", ["plain", "outbox", "streaming"])
async def test_existence_and_info_across_compaction(tmp_path, backend, wrapper):
    db, inner = await open_store(tmp_path, backend)
    store = (
        inner
        if wrapper == "plain"
        else (
            OutboxEventStore(inner)
            if wrapper == "outbox"
            else StreamingEventStore(inner)
        )
    )
    aggregate_id, other_id = uuid4(), uuid4()
    stream, other = str(aggregate_id), str(other_id)
    times = [datetime(2024, 1, day, tzinfo=UTC) for day in (1, 2, 3)]
    repo = EventSourcingRepository(Account, store)
    try:
        assert not await store.stream_exists(stream)
        assert await store.get_stream_info(stream) is None
        assert not await repo.exists(aggregate_id)
        await inner.append(
            stream,
            [
                Added(
                    aggregate_id=aggregate_id,
                    aggregate_type="Account",
                    amount=i,
                    occurred_at=t,
                )
                for i, t in enumerate(times, 1)
            ],
        )
        await inner.append(
            other, [Added(aggregate_id=other_id, aggregate_type="Account", amount=9)]
        )
        info = await store.get_stream_info(stream)
        assert (
            info.version,
            info.event_count,
            info.aggregate_type,
            info.created_at,
            info.updated_at,
        ) == (3, 3, "Account", times[0], times[-1])
        assert await store.stream_exists(stream)
        assert await repo.exists(aggregate_id)
        await inner.compact(stream, 2)
        info = await store.get_stream_info(stream)
        assert (
            info.version,
            info.event_count,
            info.aggregate_type,
            info.created_at,
            info.updated_at,
        ) == (3, 1, "Account", None, times[-1])
        assert await store.stream_exists(stream)
        assert await repo.exists(aggregate_id)
        assert (await store.get_stream_info(other)).version == 1
        await inner.compact(stream, 3)
        info = await store.get_stream_info(stream)
        assert (
            info.version,
            info.event_count,
            info.aggregate_type,
            info.created_at,
            info.updated_at,
        ) == (3, 0, None, None, None)
        assert await store.stream_exists(stream)
        assert await repo.exists(aggregate_id)
        with pytest.raises(EventStoreError, match="history"):
            await repo.get(aggregate_id)
        await inner.append(
            stream,
            [Added(aggregate_id=aggregate_id, aggregate_type="Account", amount=4)],
            expected_version=3,
        )
        info = await store.get_stream_info(stream)
        assert (info.version, info.event_count, info.created_at) == (4, 1, None)
        if db is not None:
            assert await inner.delete_stream(stream) == 1
            assert not await store.stream_exists(stream)
            assert not await repo.exists(aggregate_id)
            assert await store.get_stream_info(stream) is None
        else:
            inner.clear()
            assert not await store.stream_exists(stream)
            assert not await repo.exists(aggregate_id)
            assert await store.get_stream_info(stream) is None
    finally:
        if db is not None:
            await db.disconnect()


@pytest.mark.asyncio
async def test_repository_exists_reports_stream_not_snapshot_only():
    events, snapshots = InMemoryEventStore(), InMemorySnapshotStore()
    aggregate_id = uuid4()
    await snapshots.save_snapshot(
        Snapshot(
            aggregate_id=aggregate_id, aggregate_type="Account", version=0, state={}
        )
    )
    repo = EventSourcingRepository(Account, events, snapshots)
    assert await repo.get(aggregate_id) is not None
    assert not await repo.exists(aggregate_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [-1, True, None, "3"])
async def test_repository_exists_rejects_invalid_version(bad):
    class FakeStore:
        async def get_stream_version(self, stream_id):
            return bad

        async def read(self, *args, **kwargs):
            return []

    with pytest.raises(EventStoreError, match="version"):
        await EventSourcingRepository(Account, FakeStore()).exists(uuid4())


@pytest.mark.asyncio
async def test_repository_exists_requires_async_version_capability():
    class FakeStore:
        async def read(self, *args, **kwargs):
            return []

    with pytest.raises(EventStoreError, match="version"):
        await EventSourcingRepository(Account, FakeStore()).exists(uuid4())


@pytest.mark.asyncio
async def test_eviction_preserves_memory_info_version():
    events = InMemoryEventStore(max_events_per_stream=1)
    await events.append("s", [Added(amount=1), Added(amount=2), Added(amount=3)])
    info = await events.get_stream_info("s")
    assert (info.version, info.event_count, info.created_at) == (3, 1, None)
    assert await events.stream_exists("s")


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_sqlite_fully_compacted_info_survives_reopen(tmp_path, pooled):
    backend = "sqlite-pooled" if pooled else "sqlite"
    db, store = await open_store(tmp_path, backend)
    try:
        await store.append("s", [Added(amount=1), Added(amount=2)])
        await store.compact("s", 2)
    finally:
        await db.disconnect()
    db, store = await open_store(tmp_path, backend)
    try:
        info = await store.get_stream_info("s")
        assert (info.version, info.event_count, info.created_at, info.updated_at) == (
            2,
            0,
            None,
            None,
        )
        assert await store.stream_exists("s")
        assert await store.delete_stream("s") == 0
        assert not await store.stream_exists("s")
        assert await store.get_stream_info("s") is None
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_sqlite_stream_info_fails_on_failed_endpoint_read(tmp_path, pooled):
    from quadkit.contracts.data.sql.database import QueryResult

    db, store = await open_store(tmp_path, "sqlite-pooled" if pooled else "sqlite")
    original_query = db.execute_query
    try:
        await store.append("s", [Added(amount=1), Added(amount=2)])

        async def failed(sql, params=None):
            if "SELECT event_id, event_type, event_data" in sql:
                return QueryResult([], 0, 0.0, False, "sensitive")
            return await original_query(sql, params)

        db.execute_query = failed
        with pytest.raises(EventStoreError, match="SQLite event stream") as error:
            await store.get_stream_info("s")
        assert "sensitive" not in str(error.value)
        assert await store.stream_exists("s")  # presence is not replayability
    finally:
        db.execute_query = original_query
        await db.disconnect()


@pytest.mark.asyncio
async def test_memory_compaction_during_info_read_is_rejected():
    class ConcurrentCompaction(InMemoryEventStore):
        async def read(self, stream_id, *args, **kwargs):
            result = await super().read(stream_id, *args, **kwargs)
            await self.compact(stream_id, 1)
            return result

    events = ConcurrentCompaction(max_events_per_stream=0)
    await events.append("s", [Added(amount=1), Added(amount=2)])
    with pytest.raises(EventStoreError, match="history"):
        await events.get_stream_info("s")


@pytest.mark.asyncio
async def test_sync_version_capability_rejected_for_repository_exists():
    class FakeStore:
        def get_stream_version(self, stream_id):
            return 0

    with pytest.raises(EventStoreError, match="awaitable"):
        await EventSourcingRepository(Account, FakeStore()).exists(uuid4())
