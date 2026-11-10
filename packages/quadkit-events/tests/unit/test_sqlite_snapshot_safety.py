"""SQLite snapshot operations must not disguise failures or lose data."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from quadkit.contracts.data.sql.database import InsertResult, QueryResult
from quadkit.events.config import SqliteConfig
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.sqlite.snapshot_store import SqliteSnapshotStore
from quadkit.events.types import Snapshot
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


async def setup(path, pooled=False):
    pool = SQLiteConnectionPool(str(path)) if pooled else None
    provider = SQLiteProvider(str(path), connection_pool=pool)
    await provider.connect()
    store = SqliteSnapshotStore(
        config=SqliteConfig(snapshots_table="saved_snapshots"), provider=provider
    )
    await store.connect()
    return provider, store


def snapshot(aggregate_id, version, **kwargs):
    return Snapshot(
        aggregate_id=aggregate_id,
        aggregate_type="Order",
        version=version,
        state={"version": version, "items": [1, 2]},
        timestamp=datetime(2025, 1, 2, tzinfo=UTC),
        **kwargs,
    )


async def seed(db, aggregate_id, versions):
    for version in versions:
        result = await db.execute(
            'INSERT INTO "saved_snapshots" (aggregate_id, aggregate_type, version, state, timestamp) VALUES (?, ?, ?, ?, ?)',
            [
                str(aggregate_id),
                "Order",
                version,
                '{"version":' + str(version) + "}",
                "2025-01-02T00:00:00+00:00",
            ],
        )
        assert result.success


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_real_snapshot_save_reopen_read_and_scoped_cleanup(tmp_path, pooled):
    path = tmp_path / "snapshots.sqlite"
    db, store = await setup(path, pooled)
    a, b = uuid4(), uuid4()
    try:
        for version in (1, 2, 3):
            await store.save_snapshot(snapshot(a, version))
        await store.save_snapshot(snapshot(b, 1))
    finally:
        await db.disconnect()
    db, store = await setup(path, pooled)
    try:
        assert await store.get_latest(str(a)) == snapshot(a, 3)
        assert await store.get_by_version(a, 1) == snapshot(a, 1)
        assert await store.get_by_version(a, 999) is None
        assert await store.delete_old_snapshots(a, keep_count=2) == 1
        assert await store.get_by_version(a, 1) is None
        assert await store.get_latest(str(b)) == snapshot(b, 1)
        assert await store.delete_old_snapshots(a, keep_count=0) == 2
        assert await store.get_latest(str(a)) is None
        assert await store.get_latest(str(b)) == snapshot(b, 1)
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_failed_schema_does_not_mark_reconnected_store_connected(tmp_path):
    db, store = await setup(tmp_path / "schema.sqlite")
    original = db.execute_query

    async def failed(sql, params=None):
        return QueryResult([], 0, 0.0, False, "private detail")

    db.execute_query = failed
    try:
        with pytest.raises(EventStoreError, match="SQLite snapshot schema") as error:
            await store.connect()
        assert "private detail" not in str(error.value)
        assert not store._connected
    finally:
        db.execute_query = original
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["latest", "version"])
@pytest.mark.parametrize("partial", [False, True])
async def test_failed_read_never_returns_empty_or_partial(tmp_path, method, partial):
    db, store = await setup(tmp_path / "read.sqlite")
    original = db.execute_query

    async def failed(sql, params=None):
        return QueryResult(
            [{"untrusted": 1}] if partial else [], 0, 0.0, False, "private detail"
        )

    db.execute_query = failed
    try:
        operation = (
            store.get_latest(str(uuid4()))
            if method == "latest"
            else store.get_by_version(uuid4(), 1)
        )
        with pytest.raises(EventStoreError, match="SQLite snapshot") as error:
            await operation
        assert "private detail" not in str(error.value)
    finally:
        db.execute_query = original
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_reported_insert_failure_after_real_write_rolls_back(tmp_path, pooled):
    db, store = await setup(tmp_path / "insert.sqlite", pooled)
    aggregate_id = uuid4()
    original = db.execute_insert

    async def failed(table, data):
        result = await original(table, data)
        return InsertResult(
            result.inserted_id,
            result.affected_rows,
            result.execution_time,
            False,
            "private detail",
        )

    db.execute_insert = failed
    try:
        with pytest.raises(EventStoreError, match="SQLite snapshot") as error:
            await store.save_snapshot(snapshot(aggregate_id, 1))
        assert "private detail" not in str(error.value)
        assert await store.get_latest(str(aggregate_id)) is None
    finally:
        db.execute_insert = original
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
@pytest.mark.parametrize(
    "point", ["before_count", "delete", "after_count", "empty_count"]
)
async def test_failed_cleanup_rolls_back_real_deletion(tmp_path, pooled, point):
    db, store = await setup(tmp_path / "delete.sqlite", pooled)
    aggregate_id = uuid4()
    await seed(db, aggregate_id, [1, 2, 3])
    original_query, original_execute = db.execute_query, db.execute
    counts = 0

    async def query(sql, params=None):
        nonlocal counts
        result = await original_query(sql, params)
        if "COUNT(*)" in sql.upper():
            counts += 1
            if (point == "before_count" and counts == 1) or (
                point == "after_count" and counts == 2
            ):
                return QueryResult(
                    result.rows,
                    result.row_count,
                    result.execution_time,
                    False,
                    "private detail",
                )
            if point == "empty_count" and counts == 2:
                return QueryResult([], 0, result.execution_time, True)
        return result

    async def execute(sql, params=None):
        result = await original_execute(sql, params)
        if point == "delete" and sql.lstrip().upper().startswith("DELETE"):
            return QueryResult(
                result.rows,
                result.row_count,
                result.execution_time,
                False,
                "private detail",
            )
        return result

    db.execute_query, db.execute = query, execute
    try:
        with pytest.raises(EventStoreError, match="SQLite snapshot") as error:
            await store.delete_old_snapshots(aggregate_id, 1)
        assert "private detail" not in str(error.value)
        db.execute_query, db.execute = original_query, original_execute
        assert (await store.get_by_version(aggregate_id, 1)).version == 1
        assert (await store.get_by_version(aggregate_id, 2)).version == 2
        assert (await store.get_by_version(aggregate_id, 3)).version == 3
    finally:
        db.execute_query, db.execute = original_query, original_execute
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("keep", [-1, True, 1.5])
async def test_invalid_cleanup_count_is_rejected_without_deleting(tmp_path, keep):
    db, store = await setup(tmp_path / "invalid.sqlite")
    aggregate_id = uuid4()
    await seed(db, aggregate_id, [1, 2])
    try:
        with pytest.raises(ValueError, match="keep_count"):
            await store.delete_old_snapshots(aggregate_id, keep)
        assert (await store.get_by_version(aggregate_id, 1)).version == 1
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_nonempty_snapshot_metadata_is_rejected_not_discarded(tmp_path):
    db, store = await setup(tmp_path / "metadata.sqlite")
    aggregate_id = uuid4()
    try:
        with pytest.raises(EventStoreError, match="metadata"):
            await store.save_snapshot(
                snapshot(aggregate_id, 1, metadata={"source": "important"})
            )
        assert await store.get_latest(str(aggregate_id)) is None
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_nested_insert_failure_caught_inside_outer_transaction_does_not_commit(
    tmp_path, pooled
):
    db, store = await setup(tmp_path / "nested.sqlite", pooled)
    aggregate_id = uuid4()
    original = db.execute_insert

    async def failed(table, data):
        result = await original(table, data)
        return InsertResult(
            result.inserted_id, result.affected_rows, result.execution_time, False
        )

    try:
        async with db.transaction():
            db.execute_insert = failed
            with pytest.raises(EventStoreError, match="save SQLite snapshot"):
                await store.save_snapshot(snapshot(aggregate_id, 1))
            db.execute_insert = original
            await store.save_snapshot(snapshot(aggregate_id, 2))
        assert await store.get_by_version(aggregate_id, 1) is None
        assert (await store.get_by_version(aggregate_id, 2)).version == 2
    finally:
        db.execute_insert = original
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_duplicate_snapshot_version_does_not_replace_original(tmp_path, pooled):
    from quadkit.sql.exceptions import IntegrityError

    db, store = await setup(tmp_path / "duplicate.sqlite", pooled)
    aggregate_id = uuid4()
    original = snapshot(aggregate_id, 1)
    replacement = snapshot(aggregate_id, 1)
    replacement.state["items"] = ["different"]
    try:
        await store.save_snapshot(original)
        with pytest.raises(IntegrityError):
            await store.save_snapshot(replacement)
        assert await store.get_latest(str(aggregate_id)) == original
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_cleanup_success_report_without_deletion_fails_closed(tmp_path):
    db, store = await setup(tmp_path / "noop.sqlite")
    aggregate_id = uuid4()
    await seed(db, aggregate_id, [1, 2])
    original = db.execute

    async def noop(sql, params=None):
        if sql.lstrip().upper().startswith("DELETE"):
            return QueryResult([], 0, 0.0, True)
        return await original(sql, params)

    db.execute = noop
    try:
        with pytest.raises(EventStoreError, match="verify SQLite snapshot cleanup"):
            await store.delete_old_snapshots(aggregate_id, 1)
        assert (await store.get_by_version(aggregate_id, 1)).version == 1
        assert (await store.get_by_version(aggregate_id, 2)).version == 2
    finally:
        db.execute = original
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, -1, True, 1.5, "1"])
async def test_invalid_count_result_fails_before_delete(tmp_path, value):
    db, store = await setup(tmp_path / "count.sqlite")
    aggregate_id = uuid4()
    await seed(db, aggregate_id, [1, 2])
    original = db.execute_query

    async def malformed(sql, params=None):
        if "COUNT(*)" in sql.upper():
            return QueryResult([{"count": value}], 1, 0.0, True)
        return await original(sql, params)

    db.execute_query = malformed
    try:
        with pytest.raises(EventStoreError, match="count SQLite snapshots"):
            await store.delete_old_snapshots(aggregate_id, 1)
        assert (await store.get_by_version(aggregate_id, 1)).version == 1
    finally:
        db.execute_query = original
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("affected", [0, True])
async def test_invalid_insert_acknowledgement_rolls_back_real_write(tmp_path, affected):
    db, store = await setup(tmp_path / "bad-ack.sqlite")
    aggregate_id = uuid4()
    original = db.execute_insert

    async def invalid(table, data):
        result = await original(table, data)
        return InsertResult(result.inserted_id, affected, result.execution_time, True)

    db.execute_insert = invalid
    try:
        with pytest.raises(EventStoreError, match="save SQLite snapshot"):
            await store.save_snapshot(snapshot(aggregate_id, 1))
        assert await store.get_latest(str(aggregate_id)) is None
    finally:
        db.execute_insert = original
        await db.disconnect()
