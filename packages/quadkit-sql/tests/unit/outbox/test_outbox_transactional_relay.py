"""The outbox writes inside the caller's transaction and relays to the real bus.

Found by the first application that used it with SQLAlchemy sessions and
``quadkit-events``: the store could only write on the provider's own
executor (a second connection — not transactional at all), and the
publisher called ``publish_raw``, which ``EventBusImpl`` does not have, so
the framework's relay could not reach the framework's bus.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from quadkit.contracts.domain.events import DomainEvent
from quadkit.events.buses import EventBusImpl
from quadkit.events.config import EventBusConfig
from quadkit.sql.orm import SessionExecutor, SessionmakerExecutor
from quadkit.sql.outbox import OutboxPublisher, SQLOutboxStore


@dataclass(init=False, frozen=True)
class StockChanged(DomainEvent):
    company_id: int = 0
    product_ids: tuple[int, ...] = ()


@pytest.fixture
async def sessionmaker(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'outbox.db'}")
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        await engine.dispose()


@pytest.fixture
async def store(sessionmaker: async_sessionmaker[AsyncSession]) -> SQLOutboxStore:
    store = SQLOutboxStore(SessionmakerExecutor(sessionmaker))
    await store.create_table()
    return store


@pytest.fixture
async def bus() -> AsyncIterator[EventBusImpl]:
    bus = EventBusImpl(config=EventBusConfig(retry_failed_handlers=False))
    try:
        yield bus
    finally:
        await bus.close()


async def _pending_count(store: SQLOutboxStore) -> int:
    return len(await store.fetch_pending())


async def test_a_rolled_back_transaction_leaves_no_event(
    store: SQLOutboxStore, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    with pytest.raises(RuntimeError, match="business rule"):
        async with sessionmaker() as session, session.begin():
            await store.bound(SessionExecutor(session)).append_batch(
                [StockChanged(company_id=1, product_ids=(7,))]
            )
            msg = "business rule"
            raise RuntimeError(msg)
    assert await _pending_count(store) == 0


async def test_a_committed_transaction_leaves_one_pending_row(
    store: SQLOutboxStore, sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    async with sessionmaker() as session, session.begin():
        await store.bound(SessionExecutor(session)).append_batch([StockChanged(company_id=1, product_ids=(7, 3))])
    (row,) = await store.fetch_pending()
    assert row["event_type"] == "StockChanged"
    assert row["status"] == "pending"


async def test_the_relay_rebuilds_the_event_and_reaches_a_class_keyed_bus(
    store: SQLOutboxStore, sessionmaker: async_sessionmaker[AsyncSession], bus: EventBusImpl
) -> None:
    seen: list[StockChanged] = []

    async def handler(event: StockChanged) -> None:
        seen.append(event)

    bus.subscribe(StockChanged, handler)
    original = StockChanged(company_id=9, product_ids=(3, 7))
    async with sessionmaker() as session, session.begin():
        await store.bound(SessionExecutor(session)).append_batch([original])

    relay = OutboxPublisher(store, bus, event_types={"StockChanged": StockChanged})
    assert await relay.drain() == 1
    await bus.flush()

    (event,) = seen
    assert isinstance(event, StockChanged)
    assert event.company_id == 9
    assert tuple(event.product_ids) == (3, 7)
    assert event.event_id == original.event_id
    assert event.occurred_at == original.occurred_at
    assert await _pending_count(store) == 0


async def test_an_unknown_type_on_a_bus_without_publish_raw_is_failed_with_a_reason(
    store: SQLOutboxStore, sessionmaker: async_sessionmaker[AsyncSession], bus: EventBusImpl
) -> None:
    async with sessionmaker() as session, session.begin():
        await store.bound(SessionExecutor(session)).append_batch([StockChanged(company_id=1)])

    relay = OutboxPublisher(store, bus)  # nothing registered
    await relay.drain()

    assert await _pending_count(store) == 0
    rows = await SessionmakerExecutor(sessionmaker).fetch_all("SELECT status, error FROM outbox_events")
    assert rows[0]["status"] == "failed"
    assert "no event class registered" in rows[0]["error"]


async def test_an_err_from_publish_is_not_a_delivery(
    store: SQLOutboxStore, sessionmaker: async_sessionmaker[AsyncSession], bus: EventBusImpl
) -> None:
    async with sessionmaker() as session, session.begin():
        await store.bound(SessionExecutor(session)).append_batch([StockChanged(company_id=1)])
    await bus.close()  # publish now returns Err

    relay = OutboxPublisher(store, bus, event_types={"StockChanged": StockChanged})
    await relay.drain()

    rows = await SessionmakerExecutor(sessionmaker).fetch_all("SELECT status FROM outbox_events")
    assert rows[0]["status"] == "failed"


async def test_a_row_survives_until_a_relay_runs(
    store: SQLOutboxStore, sessionmaker: async_sessionmaker[AsyncSession], bus: EventBusImpl
) -> None:
    """The crash case: committed, no relay yet; a later relay still delivers."""
    async with sessionmaker() as session, session.begin():
        await store.bound(SessionExecutor(session)).append_batch([StockChanged(company_id=1, product_ids=(1,))])
    assert await _pending_count(store) == 1

    seen: list[StockChanged] = []

    async def handler(event: StockChanged) -> None:
        seen.append(event)

    bus.subscribe(StockChanged, handler)
    later = OutboxPublisher(store, bus)
    later.register(StockChanged)
    await later.drain()
    await bus.flush()
    assert len(seen) == 1


async def test_session_executor_rejects_positional_params(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with sessionmaker() as session:
        with pytest.raises(TypeError, match="named parameters"):
            await SessionExecutor(session).execute("SELECT :x", (1,))
        assert await SessionExecutor(session).fetch_one("SELECT :x AS x", {"x": 5}) == {"x": 5}
