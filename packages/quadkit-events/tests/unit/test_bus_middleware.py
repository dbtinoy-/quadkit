"""Middleware execution-order and result-mutation tests."""

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


class TestMiddleware:
    """Test middleware functionality"""

    @pytest.mark.asyncio
    async def test_middleware_execution_order(self):
        """Test middleware execution order"""
        bus = CommandBusImpl()

        execution_order = []

        async def middleware1(cmd, next_handler):
            execution_order.append("middleware1_start")
            result = await next_handler(cmd)
            execution_order.append("middleware1_end")
            return result

        async def middleware2(cmd, next_handler):
            execution_order.append("middleware2_start")
            result = await next_handler(cmd)
            execution_order.append("middleware2_end")
            return result

        bus.use(middleware1).use(middleware2)

        command = Command()
        handler = AsyncMock()
        handler.return_value = "result"
        bus.register(Command, handler)

        result = await bus.dispatch(command)

        assert execution_order == [
            "middleware1_start",
            "middleware2_start",
            "middleware2_end",
            "middleware1_end",
        ]
        assert result == "result"

    @pytest.mark.asyncio
    async def test_middleware_can_modify_result(self):
        """Test middleware can modify handler result"""
        bus = CommandBusImpl()

        async def result_modifier(cmd, next_handler):
            result = await next_handler(cmd)
            return f"modified_{result}"

        bus.use(result_modifier)

        command = Command()
        handler = AsyncMock()
        handler.return_value = "original"
        bus.register(Command, handler)

        result = await bus.dispatch(command)

        assert result == "modified_original"
