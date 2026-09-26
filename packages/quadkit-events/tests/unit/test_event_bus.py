"""EventBus publish, hooks, subscriptions, and dispatch-mode tests."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.contracts.events import EventBusDiagnosticsProtocol
from quadkit.events.buses import (
    CommandBusImpl,
    EventBusImpl,
    QueryBusImpl,
)
from quadkit.events.buses.base import Bus, HandlerNotFoundError
from quadkit.events.buses.command import CommandExecutionError
from quadkit.events.buses.event import EventHandlerError
from quadkit.events.buses.query import QueryExecutionError
from quadkit.events.decorators import (
    command_handler,
    event_handler,
    query_handler,
)
from quadkit.events.hooks import EventHandledHook, EventPublishedHook
from quadkit.events.messages import Command, Event, Query
from quadkit.hooks import HookRegistry

from bus_test_support import make_domain_event


class TestEventBus:
    """Test EventBusProtocol"""

    def test_event_bus_creation(self):
        """Test event bus creation"""
        bus = EventBusImpl()
        assert isinstance(bus, Bus)
        assert isinstance(bus, EventBusDiagnosticsProtocol)
        assert bus._subscribers == {}
        assert bus._global_handlers == []

    @pytest.mark.asyncio
    async def test_cancelled_dispatch_does_not_make_in_flight_negative(self):
        """Cancellation decrements the in-flight counter exactly once."""
        bus = EventBusImpl()
        started = asyncio.Event()
        release = asyncio.Event()

        async def handler(event):
            started.set()
            await release.wait()

        bus.subscribe(DomainEvent, handler)
        await bus.publish(make_domain_event(aggregate_id=uuid4()))
        await started.wait()

        drain_task = next(iter(bus._background_tasks))
        drain_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await drain_task

        assert bus._in_flight == 0

    @pytest.mark.asyncio
    async def test_event_publish(self):
        """Test basic event publication"""
        bus = EventBusImpl()
        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)
        handler = AsyncMock()

        bus.subscribe(DomainEvent, handler)

        await bus.publish(event)
        await bus.flush()  # wait for drain task to dispatch

        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_event_publish_emits_event_published_hook(self):
        """Publishing emits the canonical ``event.published`` hook."""
        received: list[EventPublishedHook] = []
        registry = HookRegistry("events-test")

        async def capture(payload: EventPublishedHook) -> None:
            received.append(payload)

        registry.register_action("event.published", capture)

        bus = EventBusImpl(hooks=registry)
        event = make_domain_event(aggregate_id=uuid4())
        handler = AsyncMock()
        bus.subscribe(DomainEvent, handler)

        result = await bus.publish(event)
        await bus.flush()

        assert result.is_ok()
        assert received == [
            EventPublishedHook(
                event_type=f"{type(event).__module__}.{type(event).__qualname__}",
                aggregate_id=str(event.aggregate_id),
            )
        ]

    @pytest.mark.asyncio
    async def test_event_publish_emits_event_handled_hook_after_successful_handler(
        self,
    ):
        """Successful handlers emit ``event.handled`` once per handler."""
        received: list[EventHandledHook] = []
        registry = HookRegistry("events-test")

        async def capture(payload: EventHandledHook) -> None:
            received.append(payload)

        async def handler(event: DomainEvent) -> None:
            return None

        registry.register_action("event.handled", capture)

        bus = EventBusImpl(hooks=registry)
        event = make_domain_event(aggregate_id=uuid4())
        bus.subscribe(DomainEvent, handler)

        result = await bus.publish(event)
        await bus.flush()

        assert result.is_ok()
        assert received == [
            EventHandledHook(
                event_type=f"{type(event).__module__}.{type(event).__qualname__}",
                handler=f"{handler.__module__}.{handler.__qualname__}",
            )
        ]

    @pytest.mark.asyncio
    async def test_failed_handler_does_not_emit_event_handled_hook(self):
        """Failed handlers do not emit ``event.handled``."""
        received: list[EventHandledHook] = []
        registry = HookRegistry("events-test")

        async def capture(payload: EventHandledHook) -> None:
            received.append(payload)

        async def failing_handler(event: DomainEvent) -> None:
            raise ValueError("boom")

        registry.register_action("event.handled", capture)

        bus = EventBusImpl(hooks=registry)
        event = make_domain_event(aggregate_id=uuid4())
        bus.subscribe(DomainEvent, failing_handler)

        result = await bus.publish(event)
        await bus.flush()

        assert result.is_ok()
        assert received == []

    @pytest.mark.asyncio
    async def test_event_publish_no_handlers(self):
        """Test event publishing with no handlers"""
        bus = EventBusImpl()
        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)

        # Should return None when no handlers
        await bus.publish(event)

    def test_subscribe_and_unsubscribe(self):
        """Test subscribing and unsubscribing handlers"""
        bus = EventBusImpl()
        handler = Mock()

        bus.subscribe(DomainEvent, handler)
        assert handler in bus._subscribers[DomainEvent]

        bus.unsubscribe(DomainEvent, handler)
        assert handler not in bus._subscribers[DomainEvent]

    def test_unsubscribe_nonexistent_handler(self):
        """Test unsubscribing a handler that doesn't exist"""
        bus = EventBusImpl()
        handler1 = Mock()
        handler2 = Mock()

        bus.subscribe(DomainEvent, handler1)
        # Try to unsubscribe handler2 which was never subscribed
        result = bus.unsubscribe(DomainEvent, handler2)
        assert result is False
        assert handler1 in bus._subscribers[DomainEvent]

    def test_subscribe_all(self):
        """Test subscribing to all events"""
        bus = EventBusImpl()
        handler = Mock()

        bus.subscribe_all(handler)
        assert handler in bus._global_handlers

    @pytest.mark.asyncio
    async def test_global_handler(self):
        """Test global event handler"""
        bus = EventBusImpl()
        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)
        handler = AsyncMock()

        bus.subscribe_all(handler)

        await bus.publish(event)
        await bus.flush()  # wait for drain task to dispatch

        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_event_publish_parallel_dispatch(self):
        """Test event publishing with parallel dispatch"""
        from quadkit.contracts.core import ExecutionStrategy
        from quadkit.concurrency import Parallel
        from quadkit.events.buses.event import EventBusConfig

        config = EventBusConfig(parallel_dispatch=True)
        bus = EventBusImpl(config=config)

        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)
        handler1 = AsyncMock()
        handler2 = AsyncMock()

        bus.subscribe(DomainEvent, handler1)
        bus.subscribe(DomainEvent, handler2)

        async def mock_execute(*args, **kwargs):
            # Close coroutines to avoid warnings
            for aw in args:
                if hasattr(aw, "close"):
                    aw.close()
            return [(handler1, None), (handler2, None)]

        with patch.object(
            Parallel, "execute", side_effect=mock_execute
        ) as mock_execute:
            await bus.publish(event)
            # flush() must be called inside the patch context so the drain
            # task runs while Parallel.execute is still mocked.
            await bus.flush()

        # Verify Parallel.execute was called with both handlers
        mock_execute.assert_called_once()
        args, kwargs = mock_execute.call_args
        assert len(args) == 2  # Two handler tasks
        assert kwargs["strategy"] == ExecutionStrategy.ALL_SETTLED

    @pytest.mark.asyncio
    async def test_event_publish_parallel_with_error_stop(self):
        """Test parallel event publishing records errors when continue_on_error=False.

        With channel-based dispatch, publish() returns immediately after enqueuing.
        Handler errors are collected in bus._dispatch_errors rather than raised
        synchronously from publish().
        """
        from quadkit.events.buses.event import EventBusConfig

        config = EventBusConfig(
            parallel_dispatch=True, continue_on_error=False, retry_failed_handlers=False
        )
        bus = EventBusImpl(config=config)

        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)

        async def handler1(e):
            raise ValueError("handler1 failed")

        async def handler2(e):
            raise ValueError("handler2 failed")

        bus.subscribe(DomainEvent, handler1)
        bus.subscribe(DomainEvent, handler2)

        await bus.publish(event)
        await bus.flush()  # wait for drain task to process

        assert len(bus.dispatch_errors) == 2
        assert all(isinstance(err, EventHandlerError) for err in bus.dispatch_errors)
        assert {err.handler for err in bus.dispatch_errors} == {
            handler1.__name__,
            handler2.__name__,
        }

    @pytest.mark.asyncio
    async def test_event_publish_parallel_with_error_continue(self):
        """Test parallel event publishing that continues on error"""
        from quadkit.events.buses.event import EventBusConfig

        config = EventBusConfig(parallel_dispatch=True, continue_on_error=True)
        bus = EventBusImpl(config=config)

        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)

        async def handler1(e):
            raise ValueError("handler1 failed")

        handler2 = AsyncMock()

        bus.subscribe(DomainEvent, handler1)
        bus.subscribe(DomainEvent, handler2)

        await bus.publish(event)
        await bus.flush()  # wait for drain task to dispatch

        handler2.assert_called_once_with(event)
        assert len(bus.dispatch_errors) == 1
        assert isinstance(bus.dispatch_errors[0], EventHandlerError)
        assert (await bus.health_check()).is_degraded()
        bus.clear_dispatch_errors()
        assert bus.dispatch_errors == ()
        assert (await bus.health_check()).is_healthy()

    @pytest.mark.asyncio
    async def test_event_publish_sequential_with_error_continue(self):
        """Test sequential event publishing that continues on error"""
        from quadkit.events.buses.event import EventBusConfig

        config = EventBusConfig(continue_on_error=True, retry_failed_handlers=False)
        bus = EventBusImpl(config=config)

        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)
        handler1 = AsyncMock()
        handler1.side_effect = ValueError("Handler 1 failed")
        handler2 = AsyncMock()

        bus.subscribe(DomainEvent, handler1)
        bus.subscribe(DomainEvent, handler2)

        await bus.publish(event)
        await bus.flush()  # wait for drain task to dispatch

        # Both handlers should have been called despite handler1 failing
        handler1.assert_called_once_with(event)
        handler2.assert_called_once_with(event)
        assert len(bus.dispatch_errors) == 1
        assert isinstance(bus.dispatch_errors[0], EventHandlerError)

    @pytest.mark.asyncio
    async def test_event_publish_sequential_with_error_stop(self):
        """Test sequential event publishing stops on error and records it.

        With channel-based dispatch, publish() returns immediately after enqueuing.
        Handler errors are collected in bus._dispatch_errors rather than raised
        synchronously from publish().
        """
        from quadkit.events.buses.event import EventBusConfig

        config = EventBusConfig(
            parallel_dispatch=False,
            continue_on_error=False,
            retry_failed_handlers=False,
        )
        bus = EventBusImpl(config=config)

        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)
        handler1 = AsyncMock()
        handler1.__name__ = "handler1"
        handler1.side_effect = ValueError("Handler 1 failed")
        handler2 = AsyncMock()

        bus.subscribe(DomainEvent, handler1)
        bus.subscribe(DomainEvent, handler2)

        await bus.publish(event)
        await bus.flush()  # wait for drain task to process

        assert len(bus._dispatch_errors) == 1
        err = bus._dispatch_errors[0]
        assert isinstance(err, EventHandlerError)
        assert err.event_type == "DomainEvent"
        assert err.handler == "handler1"
        assert "Handler 1 failed" in err.error

        # Only handler1 should have been called (continue_on_error=False)
        handler1.assert_called_once_with(event)
        handler2.assert_not_called()

    @pytest.mark.asyncio
    async def test_event_inheritance_handlers(self):
        """Test that handlers for parent event types are called"""
        bus = EventBusImpl()

        class BaseEvent(Event):
            pass

        class DerivedEvent(BaseEvent):
            pass

        base_handler = AsyncMock()
        derived_handler = AsyncMock()

        bus.subscribe(BaseEvent, base_handler)
        bus.subscribe(DerivedEvent, derived_handler)

        event = DerivedEvent(aggregate_id=uuid4())
        await bus.publish(event)
        await bus.flush()  # wait for drain task to dispatch

        # Both handlers should be called
        base_handler.assert_called_once_with(event)
        derived_handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_event_publish_respects_concurrency_limit(self):
        """Test that event publishing respects the max_concurrent_handlers limit."""
        from quadkit.events.config import EventBusConfig
        import asyncio

        config = EventBusConfig(max_concurrent_handlers=2, parallel_dispatch=True)
        bus = EventBusImpl(config=config)
        aggregate_id = uuid4()
        event = make_domain_event(aggregate_id=aggregate_id)

        concurrent_count = 0
        max_seen = 0
        lock = asyncio.Lock()

        async def slow_handler(e):
            nonlocal concurrent_count, max_seen
            async with lock:
                concurrent_count += 1
                max_seen = max(max_seen, concurrent_count)
            await asyncio.sleep(0.01)
            async with lock:
                concurrent_count -= 1
            return "done"

        # Register 5 handlers
        for _ in range(5):
            bus.subscribe(DomainEvent, slow_handler)

        await bus.publish(event)
        await bus.flush()  # wait for drain task to dispatch all handlers

        assert max_seen == 2  # Should not exceed limit of 2
