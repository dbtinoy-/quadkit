"""Real SQLite stream partitioning, global positions, and resumption."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import md5
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.checkpoints import InMemoryCheckpointStore
from quadkit.events.stores.sqlite.event_store import SqliteEventStore
from quadkit.events.streaming.subscriber import EventSubscriber
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.providers.sqlite_provider import SQLiteProvider


@dataclass(frozen=True, kw_only=True)
class ItemAdded(DomainEvent):
    label: str


@dataclass(frozen=True, kw_only=True)
class ItemRemoved(DomainEvent):
    label: str


def partition_for(stream_id: str, total: int) -> int:
    return (
        int(md5(stream_id.encode(), usedforsecurity=False).hexdigest()[:8], 16) % total
    )


async def create_store(path, pooled):
    pool = SQLiteConnectionPool(str(path)) if pooled else None
    provider = SQLiteProvider(str(path), connection_pool=pool)
    await provider.connect()
    store = SqliteEventStore(provider=provider)
    await store.connect()
    store.register_event_type("ItemAdded", ItemAdded)
    store.register_event_type("ItemRemoved", ItemRemoved)
    return provider, store


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_partition_order_batch_gaps_and_resume_after_reopening(tmp_path, pooled):
    path = tmp_path / "events.sqlite"
    provider, store = await create_store(path, pooled)
    # Select deterministic streams in each partition, then interleave them so
    # a batch can contain no matches for the partition being scanned.
    streams = [
        next(f"s-{i}" for i in range(1000) if partition_for(f"s-{i}", 3) == p)
        for p in range(3)
    ]
    try:
        for index, stream_id in enumerate(
            [streams[0], streams[0], streams[1], streams[2], streams[1], streams[0]]
        ):
            await store.append(
                stream_id, [ItemAdded(aggregate_id=uuid4(), label=str(index))]
            )
        groups = [
            [
                event
                async for event in store.stream_all(
                    batch_size=1, partition=p, total_partitions=3
                )
            ]
            for p in range(3)
        ]
        assert [[e.label for e in group] for group in groups] == [
            ["0", "1", "5"],
            ["2", "4"],
            ["3"],
        ]
        assert [[e.sequence_number for e in group] for group in groups] == [
            [1, 2, 6],
            [3, 5],
            [4],
        ]
        assert [e.sequence_number async for e in store.stream_all(batch_size=2)] == [
            1,
            2,
            3,
            4,
            5,
            6,
        ]
    finally:
        await provider.disconnect()

    provider, store = await create_store(path, pooled)
    try:
        assert [
            e.sequence_number
            async for e in store.stream_all(
                from_position=2, batch_size=1, partition=1, total_partitions=3
            )
        ] == [3, 5]
        assert [
            e.sequence_number
            async for e in store.stream_all(
                from_position=3, batch_size=1, partition=1, total_partitions=3
            )
        ] == [5]
        assert [
            e.sequence_number async for e in store.stream_all(from_position=6)
        ] == []
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_type_stream_uses_global_cursor_not_stored_event_cursor(tmp_path):
    provider, store = await create_store(tmp_path / "types.sqlite", False)
    try:
        await store.append(
            "s", [ItemRemoved(aggregate_id=uuid4(), label="a", sequence_number=999)]
        )
        await store.append(
            "s", [ItemAdded(aggregate_id=uuid4(), label="b", sequence_number=999)]
        )
        await store.append(
            "s", [ItemRemoved(aggregate_id=uuid4(), label="c", sequence_number=999)]
        )
        assert [
            e.sequence_number async for e in store.stream_by_type(["ItemRemoved"])
        ] == [1, 3]
        assert [
            e.sequence_number
            async for e in store.stream_by_type(["ItemRemoved"], from_position=1)
        ] == [3]
        assert [e async for e in store.stream_by_type([])] == []
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("partition", "total"),
    [(0, None), (None, 2), (-1, 2), (2, 2), (0, 0), (True, 2), (0, True)],
)
async def test_invalid_partition_arguments_fail_closed(tmp_path, partition, total):
    provider, store = await create_store(tmp_path / "invalid.sqlite", False)
    try:
        with pytest.raises(ValueError, match="invalid stream partition"):
            _ = [
                e
                async for e in store.stream_all(
                    partition=partition, total_partitions=total
                )
            ]
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [0, -1, True])
async def test_invalid_batch_size_fails_closed(tmp_path, size):
    provider, store = await create_store(tmp_path / "batch.sqlite", False)
    try:
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            _ = [e async for e in store.stream_all(batch_size=size)]
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_subscriber_checkpoints_and_restores_sqlite_partition(tmp_path):
    provider, store = await create_store(tmp_path / "subscriber.sqlite", False)
    checkpoints = InMemoryCheckpointStore()
    received = []
    finished = asyncio.Event()
    try:
        await store.append(
            "s", [ItemAdded(aggregate_id=uuid4(), label=str(i)) for i in range(3)]
        )
        subscriber = EventSubscriber(
            event_store=store,
            checkpoint_store=checkpoints,
            checkpoint_interval=1,
            total_partitions=1,
        )

        async def handle(event):
            received.append(event.label)
            if len(received) == 3:
                finished.set()

        subscription = await subscriber.subscribe(
            "items", handle, group_id="g", partition=0
        )
        await subscriber.start()
        try:
            await asyncio.wait_for(finished.wait(), 3)
            # checkpoint_interval=1 saves after each handler returns.
            assert subscription.position == 3
            assert await checkpoints.get_checkpoint("sub:g:items:0") == 3
        finally:
            await subscriber.stop()
        resumed = await EventSubscriber(
            event_store=store, checkpoint_store=checkpoints, total_partitions=1
        ).subscribe("items", handle, group_id="g", partition=0)
        assert resumed.position == 3
        assert [
            event
            async for event in store.stream_all(
                from_position=resumed.position, partition=0, total_partitions=1
            )
        ] == []
        assert received == ["0", "1", "2"]
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_unstampable_custom_serializer_fails_closed(tmp_path):
    provider, store = await create_store(tmp_path / "custom.sqlite", False)
    try:
        await store.append("s", [ItemAdded(aggregate_id=uuid4(), label="x")])

        class Serializer:
            def deserialize(self, event_type, data):
                return object()

        store.serializer.event_serializer = Serializer()
        with pytest.raises(EventStoreError):
            _ = [event async for event in store.stream_all()]
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_stream_cursor_is_stamped_after_upcasting_without_mutating_shared_event(
    tmp_path,
):
    provider, store = await create_store(tmp_path / "upcast.sqlite", False)
    shared = ItemAdded(aggregate_id=uuid4(), label="upcast", sequence_number=999)

    class Serializer:
        def deserialize(self, event_type, data):
            return shared

    class Registry:
        async def get_latest_version(self, event_type):
            return 2

    class Evolution:
        registry = Registry()

        async def migrate_event(self, event, latest):
            return shared

    try:
        await store.append("s", [ItemAdded(aggregate_id=uuid4(), label="stored")])
        store.serializer.event_serializer = Serializer()
        store._schema_evolution = Evolution()
        all_events = [event async for event in store.stream_all()]
        typed_events = [event async for event in store.stream_by_type(["ItemAdded"])]
        assert all_events[0].sequence_number == typed_events[0].sequence_number == 1
        assert all_events[0] is not shared
        assert typed_events[0] is not shared
        assert shared.sequence_number == 999
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_later_batch_failure_raises_after_previous_yield(tmp_path):
    from quadkit.contracts.data.sql.database import QueryResult

    provider, store = await create_store(tmp_path / "query-failure.sqlite", False)
    try:
        await store.append(
            "s", [ItemAdded(aggregate_id=uuid4(), label=str(i)) for i in range(2)]
        )
        original = provider.execute_query
        calls = 0

        async def fail_second(sql, params=None):
            nonlocal calls
            calls += 1
            if calls == 2:
                return QueryResult([], 0, 0.0, False, "secret")
            return await original(sql, params)

        provider.execute_query = fail_second
        stream = store.stream_all(batch_size=1)
        assert (await anext(stream)).sequence_number == 1
        with pytest.raises(EventStoreError, match="Could not stream"):
            await anext(stream)
    finally:
        await provider.disconnect()


@pytest.mark.asyncio
async def test_custom_serializer_shared_event_cannot_return_itself_as_copy(tmp_path):
    provider, store = await create_store(tmp_path / "unsafe-copy.sqlite", False)

    class SharedEvent:
        sequence_number = 99

        def __copy__(self):
            return self

    shared = SharedEvent()

    class Serializer:
        def deserialize(self, event_type, data):
            return shared

    try:
        await store.append("s", [ItemAdded(aggregate_id=uuid4(), label="stored")])
        store.serializer.event_serializer = Serializer()
        with pytest.raises(
            EventStoreError, match="attach SQLite event stream position"
        ):
            _ = [event async for event in store.stream_all()]
        assert shared.sequence_number == 99
    finally:
        await provider.disconnect()
