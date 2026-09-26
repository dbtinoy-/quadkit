"""Tests for distributed tracing in the event bus."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.events.buses.event import EventBusImpl
from quadkit.monitor.tracing import Span, Tracer
from quadkit.testing.fakes import FakeTracer


class _InMemorySpanExporter:
    """Simple in-memory exporter that stores exported spans for test assertions."""

    def __init__(self) -> None:
        self._finished_spans: list[Span] = []

    def export(self, spans: list[Span]) -> None:
        self._finished_spans.extend(spans)

    def get_finished_spans(self) -> list[Span]:
        return list(self._finished_spans)


@dataclass
class _Event:
    id: str = "evt-1"


@pytest.mark.asyncio
async def test_event_bus_publish_creates_span() -> None:
    """Event bus publish should record a span via the tracer."""
    tracer = FakeTracer()
    bus = EventBusImpl()
    bus.set_tracer(tracer)

    class UserCreated(_Event):
        pass

    event = UserCreated()

    result = await bus.publish(event)

    assert result.is_ok()
    assert tracer.spans[0].name == "event.publish UserCreated"


@pytest.mark.asyncio
async def test_event_bus_publish_no_tracer_works() -> None:
    """Event bus publish without tracer should work normally."""
    bus = EventBusImpl()

    class OrderPlaced(_Event):
        pass

    result = await bus.publish(OrderPlaced())

    assert result.is_ok()


@pytest.mark.asyncio
async def test_event_bus_set_tracer_clears() -> None:
    """set_tracer(None) should clear the tracer so no span is created."""
    tracer = FakeTracer()
    bus = EventBusImpl()
    bus.set_tracer(tracer)
    bus.set_tracer(None)

    class TaskFinished(_Event):
        pass

    await bus.publish(TaskFinished())

    assert len(tracer.spans) == 0


@pytest.mark.asyncio
async def test_event_bus_handler_execution_creates_span() -> None:
    """Handler execution should record an event.handle span via tracer.
    
    This test exercises the real handler dispatch path: it subscribes a handler,
    publishes an event, waits for async dispatch, and verifies that both
    publish and handle spans are created.
    """
    import asyncio
    
    tracer = FakeTracer()
    bus = EventBusImpl()
    bus.set_tracer(tracer)

    class UserDeleted(_Event):
        pass

    handler_called = False

    async def delete_user_handler(event: UserDeleted) -> None:
        nonlocal handler_called
        handler_called = True

    bus.subscribe(UserDeleted, delete_user_handler)

    event = UserDeleted()
    result = await bus.publish(event)

    assert result.is_ok()

    # Give the background drain task time to execute the handler
    await asyncio.sleep(0.1)

    assert handler_called

    # Check for both publish and handle spans
    span_names = [span.name for span in tracer.spans]
    assert "event.publish UserDeleted" in span_names
    assert "event.handle UserDeleted" in span_names


@pytest.mark.asyncio
async def test_event_bus_publish_no_handlers_closes_span() -> None:
    """Publishing an event with no handlers and allow_no_handlers=True should close the publish span.
    
    This test uses the real monitor tracer + exporter (not FakeTracer) so we can
    assert that the span has an end_time set (proving it was actually finished).
    """
    exporter = _InMemorySpanExporter()
    tracer = Tracer(service_name="test", exporter=exporter)
    bus = EventBusImpl()
    bus.set_tracer(tracer)

    class UnhandledEvent(_Event):
        pass

    # Publish an event with no registered handlers (allow_no_handlers defaults to True)
    result = await bus.publish(UnhandledEvent())

    assert result.is_ok()

    # Flush to export spans
    tracer.flush()

    # The publish span should have been exported and have an end_time
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "event.publish UnhandledEvent"
    assert spans[0].end_time is not None


__all__: list[str] = []
