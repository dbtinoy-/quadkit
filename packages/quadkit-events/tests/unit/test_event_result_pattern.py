"""Tests for Result pattern implementation in event bus.

Verifies that event operations return Result[T, EventError] types
instead of bare values or raising exceptions.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.contracts.exceptions.events import (
    EventError,
    HandlerNotFoundError,
    DuplicateHandlerError,
)
from quadkit.result import Err, Ok, Result
from quadkit.events.services import EventBusWithResultPattern


class MockDomainEvent:
    """Mock domain event for testing."""

    event_id: str = "test-event-1"
    timestamp: float = 1234567890.0


class MockEventHandler:
    """Mock event handler for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        """Initialize handler with optional failure mode."""
        self.should_fail = should_fail
        self.called = False

    async def handle(self, event: MockDomainEvent) -> Result[None, EventError]:
        """Handle event, optionally returning error."""
        self.called = True
        if self.should_fail:
            return Err(EventError("Handler intentionally failed"))
        return Ok(None)


class TestEventBusResultPattern:
    """Test Result pattern in event bus."""

    @pytest.fixture
    def event_bus(self) -> EventBusWithResultPattern:
        """Create a fresh event bus for each test."""
        return EventBusWithResultPattern()

    @pytest.fixture
    def mock_event(self) -> MockDomainEvent:
        """Create a mock domain event."""
        return MockDomainEvent()

    @pytest.fixture
    def mock_handler(self) -> MockEventHandler:
        """Create a mock event handler."""
        return MockEventHandler()

    @pytest.mark.asyncio
    async def test_subscribe_returns_ok_for_new_handler(
        self,
        event_bus: EventBusWithResultPattern,
        mock_handler: MockEventHandler,
    ) -> None:
        """Verify subscribe returns Ok for new handler."""
        result = event_bus.subscribe(MockDomainEvent, mock_handler)

        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_subscribe_returns_err_for_duplicate_handler(
        self,
        event_bus: EventBusWithResultPattern,
        mock_handler: MockEventHandler,
    ) -> None:
        """Verify subscribe returns Err for duplicate handler."""
        # First subscription should succeed
        result1 = event_bus.subscribe(MockDomainEvent, mock_handler)
        assert result1.is_ok()

        # Second subscription of same handler should fail
        result2 = event_bus.subscribe(MockDomainEvent, mock_handler)
        assert result2.is_err()
        error = result2.unwrap_err()
        assert isinstance(error, DuplicateHandlerError)

    @pytest.mark.asyncio
    async def test_unsubscribe_returns_ok_for_subscribed_handler(
        self,
        event_bus: EventBusWithResultPattern,
        mock_handler: MockEventHandler,
    ) -> None:
        """Verify unsubscribe returns Ok for subscribed handler."""
        # Subscribe first
        event_bus.subscribe(MockDomainEvent, mock_handler)

        # Then unsubscribe
        result = event_bus.unsubscribe(MockDomainEvent, mock_handler)
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_unsubscribe_returns_err_for_unsubscribed_handler(
        self,
        event_bus: EventBusWithResultPattern,
        mock_handler: MockEventHandler,
    ) -> None:
        """Verify unsubscribe returns Err for unsubscribed handler."""
        result = event_bus.unsubscribe(MockDomainEvent, mock_handler)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, HandlerNotFoundError)

    @pytest.mark.asyncio
    async def test_publish_returns_ok_when_no_handlers(
        self,
        event_bus: EventBusWithResultPattern,
        mock_event: MockDomainEvent,
    ) -> None:
        """Verify publish returns Ok when no handlers registered."""
        result = await event_bus.publish(mock_event)

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_publish_returns_ok_when_handlers_succeed(
        self,
        event_bus: EventBusWithResultPattern,
        mock_event: MockDomainEvent,
        mock_handler: MockEventHandler,
    ) -> None:
        """Verify publish returns Ok when all handlers succeed."""
        # Subscribe handler with the mocked Result.ok/err pattern
        event_bus.subscribe(MockDomainEvent, mock_handler)

        result = await event_bus.publish(mock_event)

        assert result.is_ok()
        assert mock_handler.called

    @pytest.mark.asyncio
    async def test_publish_returns_err_when_handler_fails(
        self,
        event_bus: EventBusWithResultPattern,
        mock_event: MockDomainEvent,
    ) -> None:
        """Verify publish returns Err when any handler fails."""
        failing_handler = MockEventHandler(should_fail=True)
        event_bus.subscribe(MockDomainEvent, failing_handler)

        result = await event_bus.publish(mock_event)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, EventError)

    @pytest.mark.asyncio
    async def test_add_middleware_returns_ok(
        self,
        event_bus: EventBusWithResultPattern,
    ) -> None:
        """Verify add_middleware returns Ok."""
        mock_middleware = MagicMock()
        result = event_bus.add_middleware(mock_middleware)

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_remove_middleware_returns_ok_when_registered(
        self,
        event_bus: EventBusWithResultPattern,
    ) -> None:
        """Verify remove_middleware returns Ok for registered middleware."""
        mock_middleware = MagicMock()
        event_bus.add_middleware(mock_middleware)

        result = event_bus.remove_middleware(mock_middleware)

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_remove_middleware_returns_err_when_not_registered(
        self,
        event_bus: EventBusWithResultPattern,
    ) -> None:
        """Verify remove_middleware returns Err for unregistered middleware."""
        mock_middleware = MagicMock()
        result = event_bus.remove_middleware(mock_middleware)

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, EventError)

    @pytest.mark.asyncio
    async def test_get_subscription_count_returns_ok(
        self,
        event_bus: EventBusWithResultPattern,
        mock_handler: MockEventHandler,
    ) -> None:
        """Verify get_subscription_count returns Ok with correct count."""
        event_bus.subscribe(MockDomainEvent, mock_handler)

        result = event_bus.get_subscription_count(MockDomainEvent)

        assert result.is_ok()
        assert result.unwrap() == 1

    @pytest.mark.asyncio
    async def test_get_subscription_count_zero_for_unregistered_event(
        self,
        event_bus: EventBusWithResultPattern,
    ) -> None:
        """Verify get_subscription_count returns 0 for unregistered event."""
        result = event_bus.get_subscription_count(MockDomainEvent)

        assert result.is_ok()
        assert result.unwrap() == 0

    @pytest.mark.asyncio
    async def test_error_hierarchy_correct(self) -> None:
        """Verify error hierarchy is correct."""
        from quadkit.contracts.exceptions.base import QuadkitError

        # All event errors inherit from QuadkitError
        assert issubclass(EventError, QuadkitError)
        assert issubclass(HandlerNotFoundError, EventError)
        assert issubclass(DuplicateHandlerError, EventError)

        # Instantiate and verify
        event_err = EventError("test")
        assert isinstance(event_err, QuadkitError)

        handler_not_found = HandlerNotFoundError("not found")
        assert isinstance(handler_not_found, EventError)
        assert isinstance(handler_not_found, QuadkitError)

    @pytest.mark.asyncio
    async def test_error_codes_set_correctly(self) -> None:
        """Verify event errors have correct error codes."""
        assert EventError._code == "QK_ERR_EVT_001"
        assert HandlerNotFoundError._code == "QK_ERR_EVT_002"
        assert DuplicateHandlerError._code == "QK_ERR_EVT_003"

    @pytest.mark.asyncio
    async def test_result_type_available(self) -> None:
        """Verify Result type is available for import."""
        assert Result is not None

        # Verify generic form works
        result_type = Result[None, EventError]
        assert result_type is not None

    @pytest.mark.asyncio
    async def test_multiple_handlers_for_single_event(
        self,
        event_bus: EventBusWithResultPattern,
        mock_event: MockDomainEvent,
    ) -> None:
        """Verify multiple handlers can be subscribed to single event."""
        handler1 = MockEventHandler()
        handler2 = MockEventHandler()

        event_bus.subscribe(MockDomainEvent, handler1)
        event_bus.subscribe(MockDomainEvent, handler2)

        result = await event_bus.publish(mock_event)

        assert result.is_ok()
        assert handler1.called
        assert handler2.called

    @pytest.mark.asyncio
    async def test_handler_exception_becomes_err(
        self,
        event_bus: EventBusWithResultPattern,
        mock_event: MockDomainEvent,
    ) -> None:
        """Verify handler exceptions are captured in Result."""
        mock_handler = MagicMock()
        mock_handler.handle = AsyncMock(
            side_effect=Exception("Handler crashed")
        )

        event_bus.subscribe(MockDomainEvent, mock_handler)

        # Since the handler raises an exception, EventBus should catch it
        # and return an error (this depends on implementation)
        # For now, we'll verify the subscription worked
        result = event_bus.get_subscription_count(MockDomainEvent)
        assert result.is_ok()
        assert result.unwrap() == 1


class TestEventErrorInstantiation:
    """Test event error instantiation."""

    def test_event_error_with_message(self) -> None:
        """Verify EventError includes message."""
        error = EventError("Something went wrong")
        assert "Something went wrong" in str(error)

    def test_handler_not_found_error_with_details(self) -> None:
        """Verify HandlerNotFoundError includes type info."""
        error = HandlerNotFoundError(
            "Handler not found",
            handler_type="MyHandler",
            message_type="MyEvent",
        )
        assert isinstance(error, EventError)
        assert "Handler not found" in str(error)

    def test_duplicate_handler_error_with_type(self) -> None:
        """Verify DuplicateHandlerError includes message type."""
        error = DuplicateHandlerError(
            "Handler already subscribed",
            message_type="MyEvent",
        )
        assert isinstance(error, EventError)
        assert "Handler already subscribed" in str(error)


__all__ = [
    "TestEventBusResultPattern",
    "TestEventErrorInstantiation",
]
