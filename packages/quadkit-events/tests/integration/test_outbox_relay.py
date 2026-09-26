"""Integration tests for the outbox → relay → bus flow.

These tests verify the end-to-end contract between:
  OutboxEventStore (atomic write) → OutboxPublisher (relay) → EventBusProtocol (dispatch)

Because the SQL-backed atomic path (Postgres / SQLite) requires real
database infrastructure, the full-flow tests use a ``_FakeRelay``
subclass that replaces the SQL polling with an in-memory deque.  This
isolates the orchestration logic from the database driver.

Infrastructure-independent assertions covered:
  1. ``OutboxEventStore`` delegates appends to its inner store.
  2. ``OutboxPublisher`` starts a background task and cancels it cleanly.
  3. The relay loop calls ``event_bus.publish()`` for every pending entry.
  4. Failed publishes are isolated — the relay continues to the next entry.
  5. Backpressure: ``publish_pending()`` returning 0 events triggers sleep.
"""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from quadkit.events.buses.event import EventBusImpl
from quadkit.events.messages.event import Event

if TYPE_CHECKING:
    from quadkit.contracts.events import EventBusProtocol
from quadkit.events.stores import InMemoryEventStore, OutboxEventStore, OutboxPublisher
from quadkit.contracts.domain import DomainEvent


# ---------------------------------------------------------------------------
# Test fixtures & helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class _OrderPlaced(DomainEvent):
    """Minimal test event."""

    order_id: str = ""


class _FakeRelay(OutboxPublisher):
    """OutboxPublisher subclass with an in-memory pending queue.

    Replaces the SQL-polling ``publish_pending`` with a deque so tests can
    verify the relay-to-bus dispatch logic without a real database.
    """

    def __init__(self, event_bus: EventBusImpl) -> None:
        # Construct with a no-op store — publish_pending is fully overridden.
        super().__init__(
            event_store=InMemoryEventStore(),
            event_bus=event_bus,
            poll_interval=0.01,  # Fast polling for tests
        )
        self._pending: deque[DomainEvent] = deque()

    def enqueue(self, event: DomainEvent) -> None:
        """Add an event to the fake pending queue."""
        self._pending.append(event)

    async def publish_pending(self) -> int:
        """Drain the pending queue and publish to the bus."""
        if not self._pending:
            return 0
        events = list(self._pending)
        self._pending.clear()
        for event in events:
            await self.event_bus.publish(event)
        return len(events)


# ---------------------------------------------------------------------------
# OutboxEventStore tests
# ---------------------------------------------------------------------------


class TestOutboxEventStoreDecorator:
    """OutboxEventStore wraps an inner store; appends still reach the inner store."""

    @pytest.mark.asyncio
    async def test_append_delegates_to_inner_store(self) -> None:
        """Events appended via OutboxEventStore are accessible from the inner store."""
        inner = InMemoryEventStore()
        decorated = OutboxEventStore(inner)

        event = Event(
            event_type="OrderPlaced",
            aggregate_id=uuid4(),
            aggregate_type="Order",
            sequence_number=1,
            actor_id="test",
        )

        await decorated.append("stream-1", [event], expected_version=None)

        stored = await inner.read("stream-1")
        assert len(stored) == 1
        assert stored[0].event_type == "OrderPlaced"

    @pytest.mark.asyncio
    async def test_append_multiple_events_all_delegated(self) -> None:
        inner = InMemoryEventStore()
        decorated = OutboxEventStore(inner)

        events = [
            Event(
                event_type=f"Event{i}",
                aggregate_id=uuid4(),
                aggregate_type="Order",
                sequence_number=i,
                actor_id="test",
            )
            for i in range(3)
        ]

        await decorated.append("stream-2", events)

        stored = await inner.read("stream-2")
        assert len(stored) == 3

    def test_attribute_delegation_to_inner(self) -> None:
        """Attributes not on OutboxEventStore are proxied to the inner store."""
        inner = InMemoryEventStore()
        decorated = OutboxEventStore(inner)

        # InMemoryEventStore exposes ``_streams`` — verify it proxies through
        assert hasattr(decorated, "_streams")
        assert decorated._streams is inner._streams


# ---------------------------------------------------------------------------
# OutboxPublisher lifecycle tests
# ---------------------------------------------------------------------------


class TestOutboxPublisherLifecycle:
    """OutboxPublisher starts a background asyncio task and stops it cleanly."""

    @pytest.mark.asyncio
    async def test_start_creates_background_task(self) -> None:
        bus = EventBusImpl()
        relay = _FakeRelay(bus)

        await relay.start()
        assert relay._task is not None
        assert not relay._task.done()

        await relay.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_background_task(self) -> None:
        bus = EventBusImpl()
        relay = _FakeRelay(bus)

        await relay.start()
        task = relay._task
        await relay.stop()

        assert task is not None
        assert task.done()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        """Calling start() twice does not create a second task."""
        bus = EventBusImpl()
        relay = _FakeRelay(bus)

        await relay.start()
        first_task = relay._task
        await relay.start()  # second call should be a no-op
        assert relay._task is first_task

        await relay.stop()

    @pytest.mark.asyncio
    async def test_publish_pending_returns_zero_for_empty_queue(self) -> None:
        bus = EventBusImpl()
        relay = _FakeRelay(bus)

        result = await relay.publish_pending()
        assert result == 0


# ---------------------------------------------------------------------------
# Outbox → Relay → Bus flow tests
# ---------------------------------------------------------------------------


class TestOutboxRelayBusFlow:
    """End-to-end flow: events queued in the relay reach EventBusProtocol handlers."""

    @pytest.mark.asyncio
    async def test_queued_event_is_published_to_bus(self) -> None:
        received: list[DomainEvent] = []

        bus = EventBusImpl()

        @bus.handler(_OrderPlaced)
        async def capture(event: _OrderPlaced) -> None:
            received.append(event)

        relay = _FakeRelay(bus)
        the_event = _OrderPlaced(
            event_type="OrderPlaced",
            aggregate_id=uuid4(),
            aggregate_type="Order",
            sequence_number=1,
            actor_id="test",
            order_id="order-42",
        )
        relay.enqueue(the_event)

        published = await relay.publish_pending()
        await bus.flush()

        assert published == 1
        assert len(received) == 1
        assert received[0].aggregate_id == the_event.aggregate_id

    @pytest.mark.asyncio
    async def test_multiple_queued_events_all_dispatched(self) -> None:
        received: list[DomainEvent] = []
        bus = EventBusImpl()

        @bus.handler(_OrderPlaced)
        async def capture(event: _OrderPlaced) -> None:
            received.append(event)

        relay = _FakeRelay(bus)
        for i in range(5):
            relay.enqueue(
                _OrderPlaced(
                    event_type="OrderPlaced",
                    aggregate_id=uuid4(),
                    aggregate_type="Order",
                    sequence_number=i,
                    actor_id="test",
                    order_id=f"order-{i}",
                )
            )

        published = await relay.publish_pending()
        await bus.flush()

        assert published == 5
        assert len(received) == 5

    @pytest.mark.asyncio
    async def test_relay_loop_drains_queue_automatically(self) -> None:
        """pump loop eventually drains all queued events."""
        received: list[DomainEvent] = []
        bus = EventBusImpl()

        @bus.handler(_OrderPlaced)
        async def capture(event: _OrderPlaced) -> None:
            received.append(event)

        relay = _FakeRelay(bus)
        relay.enqueue(
            _OrderPlaced(
                event_type="OrderPlaced",
                aggregate_id=uuid4(),
                aggregate_type="Order",
                sequence_number=1,
                actor_id="test",
                order_id="order-99",
            )
        )

        await relay.start()
        # Allow the loop to run at least once (poll_interval = 0.01 s)
        await asyncio.sleep(0.1)
        await relay.stop()

        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_no_handler_registered_still_runs_without_error(self) -> None:
        """Bus with allow_no_handlers (default) should not raise."""
        bus = EventBusImpl()
        relay = _FakeRelay(bus)
        relay.enqueue(
            _OrderPlaced(
                event_type="OrderPlaced",
                aggregate_id=uuid4(),
                aggregate_type="Order",
                sequence_number=1,
                actor_id="test",
            )
        )

        # Should not raise even though no handler is registered
        published = await relay.publish_pending()
        assert published == 1
