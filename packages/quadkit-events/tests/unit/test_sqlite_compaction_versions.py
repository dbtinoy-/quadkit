"""SQLite compaction preserves stream versions and reports missing history."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from quadkit.contracts.data.sql.database import DeleteResult, QueryResult
from quadkit.contracts.domain import DomainEvent
from quadkit.events.aggregates import AggregateRoot
from quadkit.events.config import SqliteConfig
from quadkit.events.exceptions import ConcurrencyError, EventStoreError
from quadkit.events.repository import EventSourcingRepository
from quadkit.events.stores.memory import InMemorySnapshotStore
from quadkit.events.stores.outbox import OutboxEventStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
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


async def open_store(path, pooled=False, *, auto_create=True):
    pool = SQLiteConnectionPool(str(path)) if pooled else None
    db = SQLiteProvider(str(path), connection_pool=pool)
    await db.connect()
    config = SqliteConfig(events_table="order_events", auto_create_tables=auto_create)
    store = SqliteEventStore(config=config, provider=db)
    await store.connect()
    store.register_event_type("Added", Added)
    return db, store


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_partial_and_full_compaction_preserve_versions_after_reopen(
    tmp_path, pooled
):
    path = tmp_path / "events.sqlite"
    db, store = await open_store(path, pooled)
    aggregate_id = uuid4()
    stream = str(aggregate_id)
    try:
        assert (
            await store.append(
                stream,
                [Added(aggregate_id=aggregate_id, amount=i) for i in (1, 2, 3)],
                expected_version=0,
            )
            == 3
        )
        assert await store.compact(stream, 2) == 2
        assert await store.get_stream_version(stream) == 3
        with pytest.raises(EventStoreError, match="history"):
            await store.read(stream)
        assert [e.amount for e in await store.read(stream, from_version=3)] == [3]
        assert await store.compact(stream, 3) == 1
        assert await store.get_stream_version(stream) == 3
        assert stream in await store.get_stream_ids()
        assert await store.read(stream, from_version=4) == []
    finally:
        await db.disconnect()
    db, store = await open_store(path, pooled)
    try:
        assert await store.get_stream_version(stream) == 3
        with pytest.raises(ConcurrencyError):
            await store.append(
                stream, [Added(aggregate_id=aggregate_id, amount=4)], expected_version=0
            )
        assert (
            await store.append(
                stream, [Added(aggregate_id=aggregate_id, amount=4)], expected_version=3
            )
            == 4
        )
        assert [e.amount for e in await store.read(stream, from_version=4)] == [4]
        with pytest.raises(EventStoreError, match="history"):
            await store.read(stream, from_version=3)
        assert await store.read(stream, limit=0) == []
        assert await store.read(stream, from_version=4, to_version=3) == []
        assert await store.delete_stream(stream) == 1
        assert await store.get_stream_version(stream) == 0
        assert stream not in await store.get_stream_ids()
        assert await store.read(stream) == []
        assert (
            await store.append(
                stream, [Added(aggregate_id=aggregate_id, amount=5)], expected_version=0
            )
            == 1
        )
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_repository_rejects_missing_history_and_accepts_covering_snapshot(
    tmp_path,
):
    db, store = await open_store(tmp_path / "snapshot.sqlite")
    aggregate_id = uuid4()
    stream = str(aggregate_id)
    snapshots = InMemorySnapshotStore()
    try:
        await store.append(
            stream, [Added(aggregate_id=aggregate_id, amount=i) for i in (1, 2, 3)]
        )
        await store.compact(stream, 2)
        with pytest.raises(EventStoreError, match="history"):
            await EventSourcingRepository(Account, store).get(aggregate_id)
        await snapshots.save_snapshot(
            Snapshot(
                aggregate_id=aggregate_id,
                aggregate_type="Account",
                version=2,
                state={"total": 3},
            )
        )
        loaded = await EventSourcingRepository(Account, store, snapshots).get(
            aggregate_id
        )
        assert loaded.id == aggregate_id
        assert loaded.version == 3
        assert loaded.total == 6
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
@pytest.mark.parametrize("where", ["marker", "deletion"])
async def test_reported_failed_compaction_rolls_back_marker_and_deletion(
    tmp_path, pooled, where
):
    db, store = await open_store(tmp_path / "rollback.sqlite", pooled)
    await store.append("s", [Added(amount=1), Added(amount=2)])
    old_execute, old_delete = db.execute, db.execute_delete

    async def execute(sql, params=None):
        result = await old_execute(sql, params)
        if (
            where == "marker"
            and "order_events_stream_state" in sql
            and sql.lstrip().upper().startswith("INSERT")
        ):
            return QueryResult(
                result.rows, result.row_count, result.execution_time, False, "private"
            )
        return result

    async def delete(*args, **kwargs):
        result = await old_delete(*args, **kwargs)
        if where == "deletion":
            return DeleteResult(result.affected_rows, result.execution_time, False)
        return result

    db.execute, db.execute_delete = execute, delete
    try:
        with pytest.raises(EventStoreError):
            await store.compact("s", 2)
        db.execute, db.execute_delete = old_execute, old_delete
        assert await store.get_stream_version("s") == 2
        assert [e.amount for e in await store.read("s")] == [1, 2]
    finally:
        db.execute, db.execute_delete = old_execute, old_delete
        await db.disconnect()


@pytest.mark.asyncio
async def test_outbox_append_after_full_compaction_uses_next_version(tmp_path):
    db, store = await open_store(tmp_path / "outbox.sqlite")
    try:
        await db.execute_query("""CREATE TABLE event_outbox (
            event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
            event_data TEXT NOT NULL, metadata TEXT NOT NULL,
            timestamp TEXT NOT NULL, status TEXT NOT NULL, published_at TEXT
        )""")
        await store.append("s", [Added(amount=1)])
        await store.compact("s", 1)
        outbox = OutboxEventStore(store)
        assert await outbox.append("s", [Added(amount=2)], expected_version=1) == 2
        assert (await db.execute_query("SELECT stream_version FROM order_events")).rows[
            0
        ]["stream_version"] == 2
        assert len((await db.execute_query("SELECT * FROM event_outbox")).rows) == 1
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_legacy_partial_compaction_is_detected_after_schema_upgrade(tmp_path):
    path = tmp_path / "legacy.sqlite"
    db, store = await open_store(path)
    try:
        await store.append("s", [Added(amount=1), Added(amount=2), Added(amount=3)])
        await db.execute('DELETE FROM "order_events" WHERE stream_version < 3')
        # Simulate a database created before stream-state metadata existed.
        await db.execute('DROP TABLE "order_events_stream_state"')
        await store.connect()
        assert await store.get_stream_version("s") == 3
        with pytest.raises(EventStoreError, match="history"):
            await store.read("s")
        assert [e.amount for e in await store.read("s", from_version=3)] == [3]
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_mixed_old_writer_after_full_compaction_is_rejected(tmp_path):
    db, store = await open_store(tmp_path / "mixed.sqlite")
    try:
        await store.append("s", [Added(amount=1), Added(amount=2)])
        await store.compact("s", 2)
        old_store = SqliteEventStore(config=store.config, provider=db)
        # Simulate an older writer that ignored the compaction marker.
        result = await db.execute(
            'INSERT INTO "order_events" (stream_id, stream_version, event_id, event_type, event_data, metadata, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)',
            ["s", 1, str(uuid4()), "Added", "{}", "{}", "2025-01-01T00:00:00+00:00"],
        )
        assert result.success
        with pytest.raises(EventStoreError, match="history"):
            await old_store.get_stream_version("s")
        with pytest.raises(EventStoreError, match="history"):
            await old_store.append("s", [Added(amount=3)])
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("noop", ["marker", "delete"])
async def test_false_success_compaction_rolls_back(tmp_path, noop):
    db, store = await open_store(tmp_path / "noop.sqlite")
    await store.append("s", [Added(amount=1), Added(amount=2)])
    original_execute, original_delete = db.execute, db.execute_delete

    async def execute(sql, params=None):
        if (
            noop == "marker"
            and "order_events_stream_state" in sql
            and sql.lstrip().upper().startswith("INSERT")
        ):
            return QueryResult([], 0, 0.0, True)
        return await original_execute(sql, params)

    async def delete(*args, **kwargs):
        if noop == "delete":
            return DeleteResult(0, 0.0, True)
        return await original_delete(*args, **kwargs)

    db.execute, db.execute_delete = execute, delete
    try:
        with pytest.raises(EventStoreError):
            await store.compact("s", 2)
        db.execute, db.execute_delete = original_execute, original_delete
        assert await store.get_stream_version("s") == 2
        assert [e.amount for e in await store.read("s")] == [1, 2]
    finally:
        db.execute, db.execute_delete = original_execute, original_delete
        await db.disconnect()


@pytest.mark.asyncio
async def test_internal_history_gap_rejects_reads_and_new_writes(tmp_path):
    db, store = await open_store(tmp_path / "gap.sqlite")
    try:
        await store.append("s", [Added(amount=1), Added(amount=2), Added(amount=3)])
        await db.execute('DELETE FROM "order_events" WHERE stream_version = 2')
        with pytest.raises(EventStoreError, match="history"):
            await store.read("s")
        with pytest.raises(EventStoreError, match="history"):
            await store.append("s", [Added(amount=4)])
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_outbox_append_outer_rollback_after_compaction(tmp_path):
    db, store = await open_store(tmp_path / "outbox-rollback.sqlite")
    try:
        await db.execute_query("""CREATE TABLE event_outbox (
            event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
            event_data TEXT NOT NULL, metadata TEXT NOT NULL,
            timestamp TEXT NOT NULL, status TEXT NOT NULL, published_at TEXT
        )""")
        await store.append("s", [Added(amount=1)])
        await store.compact("s", 1)
        with pytest.raises(ValueError, match="abort"):  # noqa: PT012
            async with db.transaction():
                await OutboxEventStore(store).append(
                    "s", [Added(amount=2)], expected_version=1
                )
                raise ValueError("abort")
        assert await store.get_stream_version("s") == 1
        assert await store.read("s", from_version=2) == []
        assert (await db.execute_query("SELECT * FROM event_outbox")).rows == []
        assert (
            await OutboxEventStore(store).append(
                "s", [Added(amount=2)], expected_version=1
            )
            == 2
        )
    finally:
        await db.disconnect()


def test_derived_stream_state_table_must_not_collide_with_snapshot_table():
    config = SqliteConfig(events_table="events", snapshots_table="EVENTS_STREAM_STATE")
    with pytest.raises(ValueError, match="tables must differ"):
        SqliteEventStore(config=config, provider=object())


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_manual_schema_requires_stream_state_migration(tmp_path, pooled):
    path = str(tmp_path / "manual.sqlite")
    pool = SQLiteConnectionPool(path) if pooled else None
    db = SQLiteProvider(path, connection_pool=pool)
    await db.connect()
    config = SqliteConfig(events_table="order_events", auto_create_tables=False)
    store = SqliteEventStore(config=config, provider=db)
    try:
        with pytest.raises(EventStoreError, match="stream-state schema"):
            await store.connect()
        for statement in store.queries.get_create_events_table_sql().split(";"):
            if statement.strip():
                assert (await db.execute_query(statement)).success
        await store.connect()
        assert await store.get_stream_version("s") == 0
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_false_success_deleting_stream_marker_rolls_back(tmp_path):
    db, store = await open_store(tmp_path / "delete-noop.sqlite")
    await store.append("s", [Added(amount=1), Added(amount=2)])
    await store.compact("s", 1)
    original = db.execute

    async def execute(sql, params=None):
        if 'DELETE FROM "order_events_stream_state"' in sql:
            return QueryResult([], 0, 0.0, True)
        return await original(sql, params)

    db.execute = execute
    try:
        with pytest.raises(EventStoreError, match="deletion"):
            await store.delete_stream("s")
        db.execute = original
        assert await store.get_stream_version("s") == 2
        assert [e.amount for e in await store.read("s", from_version=2)] == [2]
    finally:
        db.execute = original
        await db.disconnect()
