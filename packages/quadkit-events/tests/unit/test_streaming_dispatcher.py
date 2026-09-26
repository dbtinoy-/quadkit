"""Tests for events streaming dispatcher module."""

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.protocols import EventFilterProtocol
from quadkit.events.streaming import EventFilter
from quadkit.events.streaming.dispatcher import DispatcherStats, StreamDispatcher


class FakeEvent(Event):
    """Fake event for testing."""


class AnotherEvent(Event):
    """Another fake event for testing."""


class TestDispatcherStats:
    def test_dispatcher_stats_defaults(self) -> None:
        stats = DispatcherStats()
        assert stats.events_published == 0
        assert stats.events_failed == 0
        assert stats.active_subscribers == 0
        assert stats.last_event_at is None

    def test_dispatcher_stats_with_values(self) -> None:
        from datetime import UTC, datetime

        stats = DispatcherStats(
            events_published=10,
            events_failed=2,
            active_subscribers=5,
            last_event_at=datetime.now(UTC),
        )
        assert stats.events_published == 10
        assert stats.events_failed == 2
        assert stats.active_subscribers == 5


class TestStreamDispatcher:
    def test_dispatcher_initialization(self) -> None:
        dispatcher = StreamDispatcher()
        assert dispatcher._parallel_delivery is True
        assert dispatcher._continue_on_error is True
        assert dispatcher.stats.active_subscribers == 0

    def test_subscribe_specific_event(self) -> None:
        dispatcher = StreamDispatcher()

        async def handler(event: Event) -> None:
            pass

        sub_id = dispatcher.subscribe(FakeEvent, handler)
        assert sub_id is not None
        assert dispatcher.stats.active_subscribers == 1

    def test_subscribe_global(self) -> None:
        dispatcher = StreamDispatcher()

        async def handler(event: Event) -> None:
            pass

        sub_id = dispatcher.subscribe("*", handler)
        assert sub_id is not None
        assert dispatcher.stats.active_subscribers == 1

    def test_subscribe_all(self) -> None:
        dispatcher = StreamDispatcher()

        async def handler(event: Event) -> None:
            pass

        sub_id = dispatcher.subscribe_all(handler)
        assert sub_id is not None
        assert dispatcher.stats.active_subscribers == 1

    def test_unsubscribe_by_id(self) -> None:
        dispatcher = StreamDispatcher()

        async def handler(event: Event) -> None:
            pass

        sub_id = dispatcher.subscribe(FakeEvent, handler)
        result = dispatcher.unsubscribe(sub_id)
        assert result is True
        assert dispatcher.stats.active_subscribers == 0

    def test_unsubscribe_by_event_type(self) -> None:
        dispatcher = StreamDispatcher()

        async def handler(event: Event) -> None:
            pass

        dispatcher.subscribe(FakeEvent, handler)
        result = dispatcher.unsubscribe(FakeEvent, handler)
        assert result is True
        assert dispatcher.stats.active_subscribers == 0

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self) -> None:
        dispatcher = StreamDispatcher()
        event = FakeEvent()
        count = await dispatcher.publish(event)
        assert count == 0

    @pytest.mark.asyncio
    async def test_publish_with_subscriber(self) -> None:
        dispatcher = StreamDispatcher()
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe(FakeEvent, handler)
        event = FakeEvent()
        count = await dispatcher.publish(event)
        assert count == 1
        assert len(received) == 1
        assert dispatcher.stats.events_published == 1

    @pytest.mark.asyncio
    async def test_publish_batch(self) -> None:
        dispatcher = StreamDispatcher()

        async def handler(event: Event) -> None:
            pass

        dispatcher.subscribe(FakeEvent, handler)
        events = [FakeEvent(), FakeEvent(), FakeEvent()]
        count = await dispatcher.publish_batch(events)
        assert count == 3

    @pytest.mark.asyncio
    async def test_publish_inherits_parent_type(self) -> None:
        dispatcher = StreamDispatcher()
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe(Event, handler)
        event = FakeEvent()
        count = await dispatcher.publish(event)
        assert count == 1

    def test_stats_property(self) -> None:
        dispatcher = StreamDispatcher()
        stats = dispatcher.stats
        assert stats is not None
        assert isinstance(stats, DispatcherStats)

    def test_subscribe_stores_filter(self) -> None:
        dispatcher = StreamDispatcher()

        async def handler(event: Event) -> None:
            pass

        sub_id = dispatcher.subscribe(
            FakeEvent, handler, EventFilter(event_types=["FakeEvent"])
        )
        assert sub_id is not None
        assert dispatcher._subscriptions[sub_id][2] is not None

    def test_event_filter_satisfies_protocol(self) -> None:
        assert isinstance(EventFilter(event_types=["FakeEvent"]), EventFilterProtocol)
        assert isinstance(EventFilter(), EventFilterProtocol)

    @pytest.mark.asyncio
    async def test_publish_respects_filter(self) -> None:
        dispatcher = StreamDispatcher()
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe(Event, handler, EventFilter(event_types=["FakeEvent"]))
        count = await dispatcher.publish(AnotherEvent())
        assert count == 0
        assert received == []
        assert dispatcher.stats.events_published == 0
        event = FakeEvent()
        count = await dispatcher.publish(event)
        assert count == 1
        assert received == [event]
        assert dispatcher.stats.events_published == 1

    @pytest.mark.asyncio
    async def test_publish_explicit_none_filter_delivers(self) -> None:
        dispatcher = StreamDispatcher()
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe(FakeEvent, handler, None)
        event = FakeEvent()
        count = await dispatcher.publish(event)
        assert count == 1
        assert received == [event]

    @pytest.mark.asyncio
    async def test_publish_global_subscription_respects_filter(self) -> None:
        dispatcher = StreamDispatcher()
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe(
            "*",
            handler,
            EventFilter(custom_predicate=lambda e: getattr(e, "keep", False)),
        )
        count = await dispatcher.publish(FakeEvent())
        assert count == 0
        assert received == []
        count = await dispatcher.publish(FakeEvent(keep=True))
        assert count == 1
        assert received
        assert dispatcher.stats.events_published == 1

    @pytest.mark.asyncio
    async def test_publish_sequential_delivery_respects_filter(self) -> None:
        dispatcher = StreamDispatcher(parallel_delivery=False)
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe(Event, handler, EventFilter(event_types=["FakeEvent"]))
        count = await dispatcher.publish(FakeEvent())
        assert count == 1
        count = await dispatcher.publish(AnotherEvent())
        assert count == 0
        assert len(received) == 1
        assert isinstance(received[0], FakeEvent)

    @pytest.mark.asyncio
    async def test_unsubscribe_by_event_type_removes_filtered_subscription(
        self,
    ) -> None:
        dispatcher = StreamDispatcher()
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe(FakeEvent, handler, EventFilter(event_types=["FakeEvent"]))
        assert dispatcher.unsubscribe(FakeEvent, handler) is True
        count = await dispatcher.publish(FakeEvent())
        assert count == 0
        assert received == []
        assert dispatcher.stats.active_subscribers == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_all_removes_subscription_record(self) -> None:
        dispatcher = StreamDispatcher()
        received = []

        async def handler(event: Event) -> None:
            received.append(event)

        dispatcher.subscribe_all(handler)
        assert dispatcher.unsubscribe(None, handler) is True
        count = await dispatcher.publish(FakeEvent())
        assert count == 0
        assert received == []
        assert dispatcher.stats.active_subscribers == 0
