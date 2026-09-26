"""Tests for the reactive live-events admin widget."""

from __future__ import annotations

import asyncio

import pytest

from quadkit.contracts.admin import TableContent, WidgetParams
from quadkit.events.admin.handlers.live_events import LiveEventsWidgetHandler
from quadkit.events.messages.event import Event
from quadkit.events.stores.memory import InMemoryEventStore
from quadkit.events.streaming.dispatcher import StreamDispatcher


def make_event(event_type: str, aggregate_id: str = "agg-1") -> Event:
    return Event(event_type=event_type, aggregate_id=aggregate_id)


@pytest.mark.asyncio
async def test_live_events_widget_returns_table_content() -> None:
    store = InMemoryEventStore()
    await store.append(
        stream_id="agg-1",
        events=[
            make_event("OrderPlaced", "agg-1"),
            make_event("OrderClosed", "agg-1"),
        ],
        expected_version=0,
    )
    handler = LiveEventsWidgetHandler(event_store=store)

    result = await handler.get_data(WidgetParams())
    assert result.is_ok()
    content = result.unwrap()
    assert isinstance(content, TableContent)
    assert content.columns == ("Type", "Aggregate", "Actor")
    assert len(content.rows) == 2


@pytest.mark.asyncio
async def test_live_events_widget_tails_dispatcher_when_provided() -> None:
    store = InMemoryEventStore()
    dispatcher = StreamDispatcher()
    handler = LiveEventsWidgetHandler(event_store=store, dispatcher=dispatcher)

    await store.append(
        stream_id="agg-2",
        events=[make_event("OrderPlaced", "agg-2")],
        expected_version=0,
    )
    await dispatcher.publish(make_event("OrderClosed", "agg-2"))
    await asyncio.sleep(0.05)  # let the live tailing pump drain

    result = await handler.get_data(WidgetParams())
    assert result.is_ok()
    rows = result.unwrap().rows
    types = [row[0].text for row in rows]
    assert "OrderPlaced" in types and "OrderClosed" in types
