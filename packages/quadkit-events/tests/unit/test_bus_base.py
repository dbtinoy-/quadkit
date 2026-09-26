"""BaseBus handler resolution, invocation, and pipeline tests."""

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


class TestBaseBus:
    """Test base Bus functionality using concrete implementations"""

    def test_base_bus_creation(self):
        """Test base bus creation"""
        bus = CommandBusImpl()
        assert bus._middlewares == []
        assert bus._handlers == {}

    @pytest.mark.asyncio
    async def test_resolve_handler_manual_registration(self):
        """Test handler resolution from manual registrations"""
        bus = CommandBusImpl()
        handler = Mock()
        bus.register(Command, handler)

        resolved = await bus._resolve_handler(Command)
        assert resolved == handler

    @pytest.mark.asyncio
    async def test_resolve_handler_class_instantiation(self):
        """Test handler resolution with class instantiation"""
        bus = CommandBusImpl()

        class TestHandler:
            def __init__(self):
                self.value = "instantiated"

        bus.register(Command, TestHandler)
        resolved = await bus._resolve_handler(Command)

        assert isinstance(resolved, TestHandler)
        assert resolved.value == "instantiated"

    @pytest.mark.asyncio
    async def test_resolve_handler_class_instantiation_no_container(self):
        """Test handler resolution with class instantiation (no container)"""
        bus = CommandBusImpl()

        class TestHandler:
            def __init__(self):
                self.value = "instantiated"

        bus.register(Command, TestHandler)
        resolved = await bus._resolve_handler(Command)

        assert isinstance(resolved, TestHandler)
        assert resolved.value == "instantiated"

    @pytest.mark.asyncio
    async def test_resolve_handler_not_found(self):
        """Test handler resolution when not found"""
        bus = CommandBusImpl()

        with pytest.raises(HandlerNotFoundError):
            await bus._resolve_handler(Command)


    @pytest.mark.asyncio
    async def test_call_handler_function_handler(self):
        """Test calling a function handler"""
        bus = CommandBusImpl()

        async def handler_func(message):
            return "function_result"

        result = await bus._call_handler(handler_func, Command())
        assert result == "function_result"

    @pytest.mark.asyncio
    async def test_call_handler_sync_function_handler(self):
        """Test calling a synchronous function handler"""
        bus = CommandBusImpl()

        def handler_func(message):
            return "sync_result"

        result = await bus._call_handler(handler_func, Command())
        assert result == "sync_result"

    @pytest.mark.asyncio
    async def test_call_handler_object_with_handle(self):
        """Test calling an object with handle method"""
        bus = CommandBusImpl()

        class HandlerObject:
            async def handle(self, message):
                return "object_result"

        handler = HandlerObject()
        result = await bus._call_handler(handler, Command())
        assert result == "object_result"

    @pytest.mark.asyncio
    async def test_call_handler_object_with_sync_handle(self):
        """Test calling an object with synchronous handle method"""
        bus = CommandBusImpl()

        class HandlerObject:
            def handle(self, message):
                return "sync_object_result"

        handler = HandlerObject()
        result = await bus._call_handler(handler, Command())
        assert result == "sync_object_result"

    def test_call_handler_invalid_type(self):
        """Test calling an invalid handler type"""
        bus = CommandBusImpl()

        with pytest.raises(TypeError) as exc_info:
            # This should be synchronous since it's not a valid handler
            import asyncio

            asyncio.run(bus._call_handler("invalid_handler", Command()))

        assert "Invalid handler type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_pipeline_no_middlewares(self):
        """Test pipeline execution without middlewares"""
        bus = CommandBusImpl()

        async def handler(message):
            return "direct_result"

        result = await bus._execute_pipeline(Command(), handler)
        assert result == "direct_result"


    @pytest.mark.asyncio
    async def test_execute_pipeline_middleware_chain(self):
        """Test middleware chain execution in pipeline"""
        bus = CommandBusImpl()

        execution_order = []

        async def middleware1(msg, next_handler):
            execution_order.append("middleware1_start")
            result = await next_handler(msg)
            execution_order.append("middleware1_end")
            return result

        async def middleware2(msg, next_handler):
            execution_order.append("middleware2_start")
            result = await next_handler(msg)
            execution_order.append("middleware2_end")
            return result

        bus._middlewares = [middleware1, middleware2]

        async def final_handler(msg):
            execution_order.append("final_handler")
            return "chain_result"

        result = await bus._execute_pipeline(Command(), final_handler)

        assert result == "chain_result"
        assert execution_order == [
            "middleware1_start",
            "middleware2_start",
            "final_handler",
            "middleware2_end",
            "middleware1_end",
        ]


