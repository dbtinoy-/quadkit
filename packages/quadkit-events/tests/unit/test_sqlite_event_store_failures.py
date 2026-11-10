"""SQLite event-store failures must not look like empty or successful work."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from quadkit.contracts.data.sql.database import DeleteResult, QueryResult
from quadkit.contracts.domain import DomainEvent
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@dataclass(frozen=True, kw_only=True)
class Published(DomainEvent):
    title: str


async def setup(pooled: bool):
    pool = SQLiteConnectionPool(":memory:") if pooled else None
    db = SQLiteProvider(":memory:", connection_pool=pool)
    await db.connect()
    store = SqliteEventStore(provider=db)
    await store.connect()
    store.register_event_type("Published", Published)
    await store.append("stream", [Published(aggregate_id=uuid4(), title="x")])
    return db, store


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        "read",
        "stream_all",
        "partition",
        "stream_type",
        "find_type",
        "count",
        "count_stream",
        "ids",
    ],
)
@pytest.mark.parametrize("partial", [False, True])
async def test_failed_queries_do_not_become_empty_or_partial_results(
    operation, partial
):
    db, store = await setup(False)
    original = db.execute_query

    async def failed(sql, params=None):
        return QueryResult(
            [{"partial": "untrusted"}] if partial else [],
            0,
            0.0,
            False,
            "private database detail",
        )

    async def run_operation():
        if operation == "read":
            await store.read("stream")
        elif operation == "stream_all":
            _ = [event async for event in store.stream_all()]
        elif operation == "partition":
            _ = [
                event
                async for event in store.stream_all(partition=0, total_partitions=1)
            ]
        elif operation == "stream_type":
            _ = [event async for event in store.stream_by_type(["Published"])]
        elif operation == "find_type":
            await store.find_by_type("Published")
        elif operation == "count":
            await store.get_events_count()
        elif operation == "count_stream":
            await store.get_events_count("stream")
        else:
            await store.get_stream_ids()

    db.execute_query = failed
    try:
        with pytest.raises(EventStoreError) as error:
            await run_operation()
        assert "private database detail" not in str(error.value)
    finally:
        db.execute_query = original
        await db.disconnect()


@pytest.mark.asyncio
async def test_failed_schema_creation_never_marks_store_connected():
    db = SQLiteProvider(":memory:")
    await db.connect()
    original = db.execute_query

    async def failed(sql, params=None):
        return QueryResult([], 0, 0.0, False, "private database detail")

    store = SqliteEventStore(provider=db)
    await store.connect()
    db.execute_query = failed
    try:
        with pytest.raises(EventStoreError, match=r"create.*event.*schema"):
            await store.connect()
        assert not store._connected
    finally:
        db.execute_query = original
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
@pytest.mark.parametrize("method", ["delete_stream", "compact"])
async def test_reported_delete_failure_rolls_back_written_deletion(pooled, method):
    db, store = await setup(pooled)
    original_execute = db.execute
    original_delete = db.execute_delete

    async def failed_execute(sql, params=None):
        result = await original_execute(sql, params)
        if sql.lstrip().upper().startswith("DELETE"):
            return QueryResult(
                result.rows,
                result.row_count,
                result.execution_time,
                False,
                "private database detail",
            )
        return result

    async def failed_delete(*args, **kwargs):
        result = await original_delete(*args, **kwargs)
        return DeleteResult(result.affected_rows, result.execution_time, False)

    db.execute = failed_execute
    db.execute_delete = failed_delete
    try:
        operation = (
            store.delete_stream("stream")
            if method == "delete_stream"
            else store.compact("stream", up_to_version=1)
        )
        with pytest.raises(EventStoreError):
            await operation
        assert await store.get_events_count("stream") == 1
    finally:
        db.execute = original_execute
        db.execute_delete = original_delete
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_sqlite_event_read_and_compact_with_real_provider(pooled):
    db, store = await setup(pooled)
    try:
        events = await store.read("stream")
        assert len(events) == 1
        assert isinstance(events[0], Published)
        assert events[0].title == "x"
        assert len([event async for event in store.stream_all()]) == 1
        assert len([event async for event in store.stream_by_type(["Published"])]) == 1
        assert len(await store.find_by_type("Published")) == 1
        assert await store.get_stream_ids() == ["stream"]
        assert await store.compact("stream", up_to_version=1) == 1
        assert await store.get_events_count("stream") == 0
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_empty_stream_id_is_not_treated_as_all_streams():
    db, store = await setup(False)
    try:
        await store.append("", [Published(aggregate_id=uuid4(), title="empty")])
        assert await store.get_events_count("") == 1
        assert await store.get_events_count() == 2
        assert await store.delete_stream("") == 1
        assert await store.get_events_count("stream") == 1
        assert await store.get_events_count() == 1
    finally:
        await db.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_successful_deletion_and_compaction_are_stream_scoped(pooled):
    db, store = await setup(pooled)
    try:
        await store.append("stream", [Published(aggregate_id=uuid4(), title="second")])
        await store.append("other", [Published(aggregate_id=uuid4(), title="other")])
        assert await store.compact("stream", up_to_version=1) == 1
        assert await store.get_events_count("stream") == 1
        assert await store.get_events_count("other") == 1
        assert await store.delete_stream("stream") == 1
        assert await store.delete_stream("missing") == 0
        assert await store.get_events_count() == 1
        assert (await store.read("other"))[0].title == "other"
    finally:
        await db.disconnect()
