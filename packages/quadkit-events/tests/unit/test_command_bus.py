"""CommandBus dispatch, registration, and error tests."""

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


class TestCommandBus:
    """Test CommandBusProtocol"""

    def test_command_bus_creation(self):
        """Test command bus creation"""
        bus = CommandBusImpl()
        assert bus._middlewares == []
        assert bus._handlers == {}

    @pytest.mark.asyncio
    async def test_command_send(self):
        """Test command sending"""
        bus = CommandBusImpl()
        command = Command()
        handler = AsyncMock()
        handler.return_value = "result"

        bus.register(Command, handler)

        result = await bus.dispatch(command)

        handler.assert_called_once_with(command)
        assert result == "result"

    def test_register_handler_type(self):
        """Test registering handler type"""
        bus = CommandBusImpl()

        class TestHandler:
            pass

        bus.register(Command, TestHandler)
        assert bus._handlers[Command] == TestHandler

    @pytest.mark.asyncio
    async def test_command_send_handler_not_found(self):
        """Test command sending with no handler found"""
        bus = CommandBusImpl()
        command = Command()

        with pytest.raises(HandlerNotFoundError) as exc_info:
            await bus.dispatch(command)

        assert "Command" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_command_send_handler_execution_error(self):
        """Test command sending with handler execution error"""
        bus = CommandBusImpl()
        command = Command()
        handler = AsyncMock()
        handler.side_effect = ValueError("Handler error")

        bus.register(Command, handler)

        with pytest.raises(CommandExecutionError) as exc_info:
            await bus.dispatch(command)

        assert exc_info.value.command_type == "Command"
        assert "Handler error" in exc_info.value.error

    @pytest.mark.asyncio
    async def test_command_send_preserves_known_errors(self):
        """Test command sending preserves HandlerNotFoundError and CommandExecutionError"""
        bus = CommandBusImpl()
        command = Command()
        handler = AsyncMock()
        handler.side_effect = CommandExecutionError("Command", "test error")

        bus.register(Command, handler)

        with pytest.raises(CommandExecutionError):
            await bus.dispatch(command)



    @pytest.mark.asyncio
    async def test_command_bus_explicit_handler_registration(self):
        """Test explicit handler registration works correctly"""
        bus = CommandBusImpl()

        class ExplicitHandler:
            pass

        bus.register(Command, ExplicitHandler)
        resolved = await bus._resolve_handler(Command)
        assert isinstance(resolved, ExplicitHandler)


