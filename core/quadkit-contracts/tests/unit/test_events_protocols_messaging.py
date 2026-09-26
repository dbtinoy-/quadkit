"""Publisher, handler, bus, and middleware protocol tests."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.events.protocols import (
    DomainEventPublisherProtocol,
    EventBusDiagnosticsProtocol,
    EventBusProtocol,
    EventHandlerProtocol,
    EventMiddlewareProtocol,
    MultiEventHandlerProtocol,
)


class TestDomainEventPublisherProtocol:
    """Tests for DomainEventPublisherProtocol."""

    @pytest.mark.asyncio
    async def test_has_publish_method(self) -> None:
        """Test protocol has publish async method."""

        class Publisher:
            async def publish(self, event: Any) -> None:
                pass

        publisher = Publisher()
        await publisher.publish({"event": "test"})

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Publisher:
            async def publish(self, event: Any) -> None:
                pass

        assert isinstance(Publisher(), DomainEventPublisherProtocol)


class TestEventHandlerProtocol:
    """Tests for EventHandlerProtocol."""

    @pytest.mark.asyncio
    async def test_has_handle_method(self) -> None:
        """Test protocol has handle async method."""

        from quadkit.contracts.core.result import Ok

        class Handler:
            async def handle(self, event: Any) -> Any:
                return Ok(None)

        handler = Handler()
        result = await handler.handle({"event": "test"})
        assert result.is_ok()

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        from quadkit.contracts.core.result import Ok

        class Handler:
            async def handle(self, event: Any) -> Any:
                return Ok(None)

        assert isinstance(Handler(), EventHandlerProtocol)


class TestMultiEventHandlerProtocol:
    """Tests for MultiEventHandlerProtocol."""

    def test_has_handles_method(self) -> None:
        """Test protocol has handles method."""

        class Handler:
            def handles(self) -> list[type]:
                return [type("Event1", (), {}), type("Event2", (), {})]

        handler = Handler()
        result = handler.handles()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_has_handle_method(self) -> None:
        """Test protocol has handle async method."""

        from quadkit.contracts.core.result import Ok

        class Handler:
            def handles(self) -> list[type]:
                return []

            async def handle(self, event: Any) -> Any:
                return Ok(None)

        handler = Handler()
        result = await handler.handle({"event": "test"})
        assert result.is_ok()

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        from quadkit.contracts.core.result import Ok

        class Handler:
            def handles(self) -> list[type]:
                return []

            async def handle(self, event: Any) -> Any:
                return Ok(None)

        assert isinstance(Handler(), MultiEventHandlerProtocol)


class TestEventBusProtocol:
    """Tests for EventBusProtocol."""

    @pytest.mark.asyncio
    async def test_has_publish_method(self) -> None:
        """Test protocol has publish async method."""

        from quadkit.contracts.core.result import Ok

        class Bus:
            async def publish(self, event: Any) -> Any:
                return Ok(None)

        bus = Bus()
        result = await bus.publish({"event": "test"})
        assert result.is_ok()

    def test_has_subscribe_method(self) -> None:
        """Test protocol has subscribe method."""

        def dummy_handler(e: Any) -> None:
            pass

        class Bus:
            def subscribe(self, event_type: type, handler: Any) -> None:
                pass

        bus = Bus()
        bus.subscribe(type("Event", (), {}), dummy_handler)

    def test_has_unsubscribe_method(self) -> None:
        """Test protocol has unsubscribe method."""

        def dummy_handler(e: Any) -> None:
            pass

        class Bus:
            def unsubscribe(self, event_type: type, handler: Any) -> None:
                pass

        bus = Bus()
        bus.unsubscribe(type("Event", (), {}), dummy_handler)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        from quadkit.contracts.core.result import Ok

        class Bus:
            async def publish(self, event: Any) -> Any:
                return Ok(None)

            def subscribe(self, event_type: type, handler: Any) -> None:
                pass

            def unsubscribe(self, event_type: type, handler: Any) -> None:
                pass

            async def flush(self) -> None:
                pass

        assert isinstance(Bus(), EventBusProtocol)


class TestEventBusDiagnosticsProtocol:
    """Tests for the optional asynchronous dispatch diagnostics capability."""

    def test_is_runtime_checkable(self) -> None:
        """A bus can expose diagnostics without changing EventBusProtocol."""

        class Bus:
            @property
            def dispatch_errors(self) -> tuple[Exception, ...]:
                return ()

            def clear_dispatch_errors(self) -> None:
                pass

        assert isinstance(Bus(), EventBusDiagnosticsProtocol)


class TestEventMiddlewareProtocol:
    """Tests for EventMiddlewareProtocol."""

    @pytest.mark.asyncio
    async def test_has_call_method(self) -> None:
        """Test protocol has __call__ async method."""

        async def noop_next(event: Any) -> None:
            pass

        class Middleware:
            async def __call__(self, event: Any, next_handler: Any) -> None:
                pass

        middleware = Middleware()
        await middleware({"event": "test"}, noop_next)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Middleware:
            async def __call__(self, event: Any, next_handler: Any) -> None:
                pass

        assert isinstance(Middleware(), EventMiddlewareProtocol)
