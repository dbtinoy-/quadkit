"""Unit tests for command and query bus implementations."""

from unittest.mock import AsyncMock

import pytest

from quadkit.events import (
    Command,
    CommandBusImpl,
    CommandExecutionError,
    HandlerNotFoundError,
    Query,
    QueryBusImpl,
    QueryExecutionError,
)
from quadkit.events.buses.command import CommandExecutionError
from quadkit.events.buses.query import QueryExecutionError


class TestCommandBus:
    """Test CommandBusImpl dispatch and handlers."""

    def test_command_bus_creation(self):
        """Test command bus initialization."""
        bus = CommandBusImpl()
        assert bus._middlewares == []
        assert bus._handlers == {}

    @pytest.mark.asyncio
    async def test_dispatch_command(self):
        """Test dispatching a command to its handler."""
        bus = CommandBusImpl()
        command = Command()
        handler = AsyncMock()
        handler.return_value = "command_result"

        bus.register(Command, handler)
        result = await bus.dispatch(command)

        handler.assert_called_once_with(command)
        assert result == "command_result"

    @pytest.mark.asyncio
    async def test_dispatch_multiple_commands(self):
        """Test dispatching multiple commands of same type."""
        bus = CommandBusImpl()

        class CustomCommand(Command):
            pass

        handler = AsyncMock(return_value="handled")

        bus.register(CustomCommand, handler)

        cmd1 = CustomCommand()
        cmd2 = CustomCommand()

        result1 = await bus.dispatch(cmd1)
        result2 = await bus.dispatch(cmd2)

        assert handler.call_count == 2
        assert result1 == "handled"
        assert result2 == "handled"

    @pytest.mark.asyncio
    async def test_dispatch_handler_not_found(self):
        """Test dispatch raises error when no handler registered."""
        bus = CommandBusImpl()
        command = Command()

        with pytest.raises(HandlerNotFoundError) as exc_info:
            await bus.dispatch(command)

        assert "Command" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dispatch_handler_execution_error(self):
        """Test dispatch wraps handler errors in CommandExecutionError."""
        bus = CommandBusImpl()
        command = Command()
        handler = AsyncMock()
        handler.side_effect = ValueError("handler failed")

        bus.register(Command, handler)

        with pytest.raises(CommandExecutionError) as exc_info:
            await bus.dispatch(command)

        assert exc_info.value.command_type == "Command"
        assert "handler failed" in exc_info.value.error

    @pytest.mark.asyncio
    async def test_dispatch_preserves_known_errors(self):
        """Test dispatch preserves CommandExecutionError without wrapping."""
        bus = CommandBusImpl()
        command = Command()
        handler = AsyncMock()
        handler.side_effect = CommandExecutionError(command_type="Command", error="known error")

        bus.register(Command, handler)

        with pytest.raises(CommandExecutionError) as exc_info:
            await bus.dispatch(command)

        assert exc_info.value.command_type == "Command"
        assert exc_info.value.error == "known error"

    def test_register_handler_type(self):
        """Test registering a handler class."""
        bus = CommandBusImpl()

        class TestHandler:
            pass

        bus.register(Command, TestHandler)
        assert bus._handlers[Command] == TestHandler

    @pytest.mark.asyncio
    async def test_resolve_handler_instance(self):
        """Test handler resolution instantiates class."""
        bus = CommandBusImpl()

        class InstanceHandler:
            def __init__(self):
                self.value = "instance_created"

        bus.register(Command, InstanceHandler)
        resolved = await bus._resolve_handler(Command)

        assert isinstance(resolved, InstanceHandler)
        assert resolved.value == "instance_created"

    @pytest.mark.asyncio
    async def test_call_handler_async_function(self):
        """Test calling async function handler."""
        bus = CommandBusImpl()

        async def handler_func(msg):
            return "async_result"

        result = await bus._call_handler(handler_func, Command())
        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_call_handler_sync_function(self):
        """Test calling sync function handler."""
        bus = CommandBusImpl()

        def handler_func(msg):
            return "sync_result"

        result = await bus._call_handler(handler_func, Command())
        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_call_handler_object_with_handle(self):
        """Test calling object with handle method."""
        bus = CommandBusImpl()

        class HandlerObject:
            async def handle(self, message):
                return "object_result"

        handler = HandlerObject()
        result = await bus._call_handler(handler, Command())
        assert result == "object_result"


class TestQueryBus:
    """Test QueryBusImpl query dispatch and result handling."""

    def test_query_bus_creation(self):
        """Test query bus initialization."""
        bus = QueryBusImpl()
        assert bus._middlewares == []
        assert bus._handlers == {}

    @pytest.mark.asyncio
    async def test_execute_query(self):
        """Test executing a query with its handler."""
        bus = QueryBusImpl()
        query = Query()
        handler = AsyncMock()
        handler.return_value = "query_result"

        bus.register(Query, handler)
        result = await bus.execute(query)

        handler.assert_called_once_with(query)
        assert result == "query_result"

    @pytest.mark.asyncio
    async def test_execute_multiple_queries(self):
        """Test executing multiple queries of same type."""
        bus = QueryBusImpl()

        class CustomQuery(Query):
            pass

        handler = AsyncMock(return_value="query_data")

        bus.register(CustomQuery, handler)

        q1 = CustomQuery()
        q2 = CustomQuery()

        result1 = await bus.execute(q1)
        result2 = await bus.execute(q2)

        assert handler.call_count == 2
        assert result1 == "query_data"
        assert result2 == "query_data"

    @pytest.mark.asyncio
    async def test_execute_handler_not_found(self):
        """Test execute raises error when no handler registered."""
        bus = QueryBusImpl()
        query = Query()

        with pytest.raises(HandlerNotFoundError) as exc_info:
            await bus.execute(query)

        assert "Query" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_handler_execution_error(self):
        """Test execute wraps handler errors in QueryExecutionError."""
        bus = QueryBusImpl()
        query = Query()
        handler = AsyncMock()
        handler.side_effect = RuntimeError("query failed")

        bus.register(Query, handler)

        with pytest.raises(QueryExecutionError) as exc_info:
            await bus.execute(query)

        assert exc_info.value.query_type == "Query"
        assert "query failed" in exc_info.value.error

    @pytest.mark.asyncio
    async def test_execute_preserves_known_errors(self):
        """Test execute preserves QueryExecutionError without wrapping."""
        bus = QueryBusImpl()
        query = Query()
        handler = AsyncMock()
        handler.side_effect = QueryExecutionError(query_type="Query", error="known error")

        bus.register(Query, handler)

        with pytest.raises(QueryExecutionError) as exc_info:
            await bus.execute(query)

        assert exc_info.value.query_type == "Query"
        assert exc_info.value.error == "known error"

    def test_register_handler_type(self):
        """Test registering a handler class."""
        bus = QueryBusImpl()

        class TestHandler:
            pass

        bus.register(Query, TestHandler)
        assert bus._handlers[Query] == TestHandler

    @pytest.mark.asyncio
    async def test_resolve_handler_instance(self):
        """Test handler resolution instantiates class."""
        bus = QueryBusImpl()

        class InstanceHandler:
            def __init__(self):
                self.data = "query_handler_data"

        bus.register(Query, InstanceHandler)
        resolved = await bus._resolve_handler(Query)

        assert isinstance(resolved, InstanceHandler)
        assert resolved.data == "query_handler_data"

    @pytest.mark.asyncio
    async def test_call_handler_async_function(self):
        """Test calling async function handler."""
        bus = QueryBusImpl()

        async def handler_func(msg):
            return "async_query_result"

        result = await bus._call_handler(handler_func, Query())
        assert result == "async_query_result"

    @pytest.mark.asyncio
    async def test_call_handler_sync_function(self):
        """Test calling sync function handler."""
        bus = QueryBusImpl()

        def handler_func(msg):
            return "sync_query_result"

        result = await bus._call_handler(handler_func, Query())
        assert result == "sync_query_result"

    @pytest.mark.asyncio
    async def test_call_handler_object_with_handle(self):
        """Test calling object with handle method."""
        bus = QueryBusImpl()

        class QueryHandlerObject:
            async def handle(self, query):
                return "object_query_result"

        handler = QueryHandlerObject()
        result = await bus._call_handler(handler, Query())
        assert result == "object_query_result"
