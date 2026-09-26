import asyncio
import os
from typing import Any, AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio


def make_domain_event(*, aggregate_id: Any | None = None, **kwargs) -> Any:
    """Test helper: construct a DomainEvent while avoiding strict constructor typing for mypy."""
    from quadkit.contracts.domain import DomainEvent

    if aggregate_id is None:
        aggregate_id = uuid4()

    data = {
        "aggregate_id": aggregate_id,
        "aggregate_type": kwargs.get("aggregate_type", "TestAggregate"),
        "version": kwargs.get("version", 0),
        "event_type": kwargs.get("event_type", None),
        "sequence_number": kwargs.get("sequence_number", None),
        "actor_id": kwargs.get("actor_id", None),
    }
    data.update(kwargs)
    return DomainEvent(**data)


from quadkit.events.stores import (
    PostgresEventStoreConfig,
    PostgresEventStore,
)

TEST_DSN = os.environ.get("TEST_POSTGRES_DSN")


@pytest_asyncio.fixture
async def pg_store() -> AsyncGenerator[PostgresEventStore, None]:
    if not TEST_DSN:
        pytest.skip("TEST_POSTGRES_DSN not set; skipping Postgres integration tests")

    config = PostgresEventStoreConfig(dsn=TEST_DSN, pool_min_size=1, pool_max_size=2)
    event_store = PostgresEventStore(config)
    await event_store.connect()

    # Truncate table before running tests to ensure isolation
    async with event_store._pool.acquire() as conn:
        await conn.execute(f"TRUNCATE TABLE {config.events_table} RESTART IDENTITY")

    try:
        yield event_store

    finally:
        # Cleanup
        async with event_store._pool.acquire() as conn:
            await conn.execute(f"TRUNCATE TABLE {config.events_table} RESTART IDENTITY")
        await event_store.close()


@pytest.mark.asyncio
async def test_global_sequence_is_monotonic(pg_store: PostgresEventStore) -> None:
    e1 = make_domain_event()
    e2 = make_domain_event()

    res1 = await pg_store.save("order_1", [e1], expected_version=0)
    res2 = await pg_store.save("payment_1", [e2], expected_version=0)

    # Ensure we received stored event metadata
    assert res1 and res2
    assert res1[0].global_sequence != res2[0].global_sequence

    events = await pg_store.find_events_since(0)
    assert len(events) >= 2

    # Find first event for each stream
    first_order = next((e for e in events if e.stream_id == "order_1"), None)
    first_payment = next((e for e in events if e.stream_id == "payment_1"), None)

    assert first_order is not None and first_payment is not None
    assert first_payment.global_sequence != first_order.global_sequence


@pytest.mark.asyncio
async def test_concurrent_appends_have_unique_global_sequences(
    pg_store: PostgresEventStore,
) -> None:
    async def append_one(i: int):
        stream = f"agg_{i}_{uuid4().hex}"
        e = make_domain_event()
        stored = await pg_store.save(stream, [e], expected_version=0)
        return stored

    tasks = list(map(append_one, range(10)))
    results = await asyncio.gather(*tasks)

    # Flatten returned stored events and ensure uniqueness
    from itertools import chain
    returned_global_seqs = list(map(lambda ev: ev.global_sequence, chain.from_iterable(results)))
    assert len(returned_global_seqs) == len(set(returned_global_seqs))

    events = await pg_store.find_events_since(0, limit=100)
    global_seqs = list(map(lambda e: e.global_sequence, events))
    assert len(global_seqs) == len(set(global_seqs))


@pytest.mark.asyncio
async def test_find_events_since_returns_in_global_order(
    pg_store: PostgresEventStore,
) -> None:
    await pg_store.save("order_1", [make_domain_event()], expected_version=0)
    await pg_store.save("payment_1", [make_domain_event()], expected_version=0)
    await pg_store.save("order_2", [make_domain_event()], expected_version=0)

    events = await pg_store.find_events_since(0)
    sequences = list(map(lambda e: e.global_sequence, events))
    assert sequences == sorted(sequences)
