"""Unit tests for event streaming."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.streaming.dispatcher import StreamDispatcher, DispatcherStats


class _TestEvent(Event):
    """Test event."""

    value: str = "test"


class TestDispatcherStats:
    """Test DispatcherStats functionality."""

    def test_stats_creation(self):
        """Test creating dispatcher stats."""
        timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        stats = DispatcherStats(
            events_published=10,
            events_failed=2,
            active_subscribers=5,
            last_event_at=timestamp,
        )

        assert stats.events_published == 10
        assert stats.events_failed == 2
        assert stats.active_subscribers == 5
        assert stats.last_event_at == timestamp

    def test_stats_defaults(self):
        """Test stats default values."""
        stats = DispatcherStats()
        assert stats.events_published == 0
        assert stats.events_failed == 0
        assert stats.active_subscribers == 0
        assert stats.last_event_at is None


class TestStreamDispatcher:
    """Test StreamDispatcher functionality."""

    def test_dispatcher_initialization(self):
        """Test dispatcher initialization."""
        dispatcher = StreamDispatcher()
        assert dispatcher._subscribers == {}
        assert dispatcher._global_subscribers == []
        assert isinstance(dispatcher.stats, DispatcherStats)

    def test_subscribe_to_event_type(self):
        """Test subscribing to specific event type."""
        dispatcher = StreamDispatcher()
        handler = MagicMock()

        dispatcher.subscribe(_TestEvent, handler)

        assert _TestEvent in dispatcher._subscribers
        assert handler in dispatcher._subscribers[_TestEvent]

    def test_subscribe_all(self):
        """Test subscribing to all events."""
        dispatcher = StreamDispatcher()
        handler = MagicMock()

        dispatcher.subscribe_all(handler)

        assert handler in dispatcher._global_subscribers

    def test_unsubscribe_from_event_type(self):
        """Test unsubscribing from specific event type."""
        dispatcher = StreamDispatcher()
        handler = MagicMock()

        dispatcher.subscribe(_TestEvent, handler)
        assert handler in dispatcher._subscribers[_TestEvent]

        dispatcher.unsubscribe(_TestEvent, handler)
        assert handler not in dispatcher._subscribers[_TestEvent]

    def test_unsubscribe_all(self):
        """Test unsubscribing from all events."""
        dispatcher = StreamDispatcher()
        handler = MagicMock()

        dispatcher.subscribe_all(handler)
        assert handler in dispatcher._global_subscribers

        result = dispatcher.unsubscribe(None, handler)
        assert result is True
        assert handler not in dispatcher._global_subscribers

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """Test publishing an event."""
        dispatcher = StreamDispatcher()
        handler = AsyncMock()

        dispatcher.subscribe(_TestEvent, handler)
        event = _TestEvent(aggregate_id=uuid4(), value="test_value")

        await dispatcher.publish(event)

        handler.assert_called_once_with(event)
        assert dispatcher.stats.events_published == 1
        assert dispatcher.stats.last_event_at is not None

    @pytest.mark.asyncio
    async def test_publish_event_multiple_handlers(self):
        """Test publishing to multiple handlers."""
        dispatcher = StreamDispatcher()
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        dispatcher.subscribe(_TestEvent, handler1)
        dispatcher.subscribe(_TestEvent, handler2)

        event = _TestEvent(aggregate_id=uuid4())
        await dispatcher.publish(event)

        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)
        assert dispatcher.stats.events_published == 1

    @pytest.mark.asyncio
    async def test_publish_global_subscribers(self):
        """Test publishing to global subscribers."""
        dispatcher = StreamDispatcher()
        global_handler = AsyncMock()
        specific_handler = AsyncMock()

        dispatcher.subscribe_all(global_handler)
        dispatcher.subscribe(_TestEvent, specific_handler)

        event = _TestEvent(aggregate_id=uuid4())
        await dispatcher.publish(event)

        global_handler.assert_called_once_with(event)
        specific_handler.assert_called_once_with(event)
        assert dispatcher.stats.events_published == 1

    @pytest.mark.asyncio
    async def test_publish_handler_failure(self):
        """Test handling handler failures."""
        dispatcher = StreamDispatcher()
        failing_handler = AsyncMock(side_effect=Exception("Handler failed"))
        success_handler = AsyncMock()

        dispatcher.subscribe(_TestEvent, failing_handler)
        dispatcher.subscribe(_TestEvent, success_handler)

        event = _TestEvent(aggregate_id=uuid4())
        await dispatcher.publish(event)

        failing_handler.assert_called_once_with(event)
        success_handler.assert_called_once_with(event)
        assert dispatcher.stats.events_failed == 1
        assert dispatcher.stats.events_published == 1

    def test_get_subscriber_count(self):
        """Test getting subscriber count."""
        dispatcher = StreamDispatcher()

        assert dispatcher.stats.active_subscribers == 0

        dispatcher.subscribe(_TestEvent, MagicMock())
        dispatcher.subscribe_all(MagicMock())

        assert dispatcher.stats.active_subscribers == 2

    def test_clear_subscribers(self):
        """Test clearing all subscribers."""
        dispatcher = StreamDispatcher()

        dispatcher.subscribe(_TestEvent, MagicMock())
        dispatcher.subscribe_all(MagicMock())

        assert dispatcher.stats.active_subscribers == 2

        # Clear by unsubscribing each one
        dispatcher.unsubscribe(_TestEvent, dispatcher._subscribers[_TestEvent][0])
        dispatcher.unsubscribe(None, dispatcher._global_subscribers[0])

        assert dispatcher.stats.active_subscribers == 0
        # Check that subscribers are cleared (empty lists are Ok, but should be empty)
        assert all(len(handlers) == 0 for handlers in dispatcher._subscribers.values())
        assert dispatcher._global_subscribers == []
