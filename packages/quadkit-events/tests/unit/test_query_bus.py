"""QueryBus dispatch, registration, and error tests."""

from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from quadkit.contracts.domain import DomainEvent
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


class TestQueryBus:
    """Test QueryBusProtocol"""

    def test_query_bus_creation(self):
        """Test query bus creation"""
        bus = QueryBusImpl()
        assert bus._middlewares == []
        assert bus._handlers == {}

    @pytest.mark.asyncio
    async def test_query_send(self):
        """Test query sending"""
        bus = QueryBusImpl()
        query = Query()
        handler = AsyncMock()
        handler.return_value = "result"

        bus.register(Query, handler)

        result = await bus.execute(query)

        handler.assert_called_once_with(query)
        assert result == "result"

    def test_register_handler_type(self):
        """Test registering handler type"""
        bus = QueryBusImpl()

        class TestHandler:
            pass

        bus.register(Query, TestHandler)
        assert bus._handlers[Query] == TestHandler

    @pytest.mark.asyncio
    async def test_query_send_handler_not_found(self):
        """Test query sending with no handler found"""
        bus = QueryBusImpl()
        query = Query()

        with pytest.raises(HandlerNotFoundError) as exc_info:
            await bus.execute(query)

        assert "Query" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_query_send_handler_execution_error(self):
        """Test query sending with handler execution error"""
        bus = QueryBusImpl()
        query = Query()
        handler = AsyncMock()
        handler.side_effect = ValueError("Handler error")

        bus.register(Query, handler)

        with pytest.raises(QueryExecutionError) as exc_info:
            await bus.execute(query)

        assert exc_info.value.query_type == "Query"
        assert "Handler error" in exc_info.value.error

    @pytest.mark.asyncio
    async def test_query_send_preserves_known_errors(self):
        """Test query sending preserves HandlerNotFoundError and QueryExecutionError"""
        bus = QueryBusImpl()
        query = Query()
        handler = AsyncMock()
        handler.side_effect = QueryExecutionError("Query", "test error")

        bus.register(Query, handler)

        with pytest.raises(QueryExecutionError):
            await bus.execute(query)



    @pytest.mark.asyncio
    async def test_query_bus_explicit_handler_registration(self):
        """Test explicit handler registration works correctly"""
        bus = QueryBusImpl()

        class ExplicitHandler:
            pass

        bus.register(Query, ExplicitHandler)
        resolved = await bus._resolve_handler(Query)
        assert isinstance(resolved, ExplicitHandler)


