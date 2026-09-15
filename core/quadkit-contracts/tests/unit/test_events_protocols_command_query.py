"""Command and query handler/bus protocol tests."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.events.protocols import (
    AggregateFactoryProtocol,
    CommandBusProtocol,
    CommandHandlerProtocol,
    DomainEventPublisherProtocol,
    EventBusProtocol,
    EventHandlerProtocol,
    EventMiddlewareProtocol,
    EventSourcedReadRepositoryProtocol,
    EventSourcedRepositoryProtocol,
    EventStoreProtocol,
    IntegrationEventProtocol,
    MultiEventHandlerProtocol,
    ProjectionProtocol,
    PubSubProtocol,
    QueryBusProtocol,
    QueryHandlerProtocol,
    SnapshotStoreProtocol,
    WebhookSignatureVerifierProtocol,
)




class TestCommandHandlerProtocol:
    """Tests for CommandHandlerProtocol."""

    @pytest.mark.asyncio
    async def test_has_handle_method(self) -> None:
        """Test protocol has handle async method."""

        class Handler:
            async def handle(self, command: Any) -> Any:
                return {"status": "handled"}

        handler = Handler()
        result = await handler.handle({"command": "test"})
        assert result["status"] == "handled"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Handler:
            async def handle(self, command: Any) -> Any:
                return {}

        assert isinstance(Handler(), CommandHandlerProtocol)


class TestCommandBusProtocol:
    """Tests for CommandBusProtocol."""

    @pytest.mark.asyncio
    async def test_has_dispatch_method(self) -> None:
        """Test protocol has dispatch async method."""

        class Bus:
            async def dispatch(self, command: Any) -> Any:
                return {"status": "dispatched"}

        bus = Bus()
        result = await bus.dispatch({"command": "test"})
        assert result["status"] == "dispatched"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Bus:
            async def dispatch(self, command: Any) -> Any:
                return {}

        assert isinstance(Bus(), CommandBusProtocol)


class TestQueryHandlerProtocol:
    """Tests for QueryHandlerProtocol."""

    @pytest.mark.asyncio
    async def test_has_handle_method(self) -> None:
        """Test protocol has handle async method."""

        class Handler:
            async def handle(self, query: Any) -> Any:
                return {"data": "test"}

        handler = Handler()
        result = await handler.handle({"query": "test"})
        assert result["data"] == "test"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Handler:
            async def handle(self, query: Any) -> Any:
                return {}

        assert isinstance(Handler(), QueryHandlerProtocol)


class TestQueryBusProtocol:
    """Tests for QueryBusProtocol."""

    @pytest.mark.asyncio
    async def test_has_execute_method(self) -> None:
        """Test protocol has execute async method."""

        class Bus:
            async def execute(self, query: Any) -> Any:
                return {"data": "test"}

        bus = Bus()
        result = await bus.execute({"query": "test"})
        assert result["data"] == "test"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Bus:
            async def execute(self, query: Any) -> Any:
                return {}

        assert isinstance(Bus(), QueryBusProtocol)


