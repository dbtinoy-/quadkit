"""Tests for quadkit.events.reactive bridges."""

from __future__ import annotations

import asyncio

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.reactive import from_bus, from_store
from quadkit.events.stores.memory import InMemoryEventStore
from quadkit.events.streaming.dispatcher import StreamDispatcher


@pytest.mark.asyncio
async def test_from_store_streams_replayed_events() -> None:
    store = InMemoryEventStore()
    await store.append(
        stream_id="order-1",
        events=[
            Event(event_type="OrderPlaced", aggregate_id="1"),
            Event(event_type="OrderClosed", aggregate_id="1"),
        ],
        expected_version=0,
    )
    stream = from_store(store)
    events = [e async for e in stream]
    assert [e.event_type for e in events] == ["OrderPlaced", "OrderClosed"]


@pytest.mark.asyncio
async def test_from_store_filters_by_type() -> None:
    store = InMemoryEventStore()
    await store.append(
        stream_id="order-1",
        events=[
            Event(event_type="OrderPlaced", aggregate_id="1"),
            Event(event_type="OrderClosed", aggregate_id="1"),
        ],
        expected_version=0,
    )
    stream = from_store(store, event_types=["OrderPlaced"])
    events = [e async for e in stream]
    assert [e.event_type for e in events] == ["OrderPlaced"]


@pytest.mark.asyncio
async def test_from_bus_catches_up_then_tails_live() -> None:
    store = InMemoryEventStore()
    dispatcher = StreamDispatcher()
    seen: list[Event] = []

    await store.append(
        stream_id="order-1",
        events=[Event(event_type="OrderPlaced", aggregate_id="1")],
        expected_version=0,
    )

    async def drain() -> None:
        async for e in from_bus(dispatcher, store):
            seen.append(e)

    task = asyncio.create_task(drain())
    await asyncio.sleep(0.05)

    await dispatcher.publish(Event(event_type="OrderClosed", aggregate_id="1"))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert [e.event_type for e in seen] == ["OrderPlaced", "OrderClosed"]
