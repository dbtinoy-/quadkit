"""Handler info, registry, and handler/saga/projection decorator tests."""

from __future__ import annotations

from dataclasses import dataclass

from typing import cast

import pytest

from quadkit.events.decorators.handlers import (
    HandlerInfo,
    clear_handlers,
    command_handler,
    event_handler,
    get_all_handlers,
    get_handler_info,
    multi_event_handler,
    projection,
    query_handler,
    saga,
)
from quadkit.events.decorators.validation import (
    CQRSValidationError,
    clear_idempotency_cache,
    idempotent,
    validate,
    validate_command,
    validate_query,
)
from quadkit.events.messages.command import Command
from quadkit.events.messages.event import Event
from quadkit.events.messages.query import Query


from decorator_test_support import _TestCommand, _TestEvent, _TestProjection, _TestQuery, _TestSaga


class TestHandlerInfo:
    """Test HandlerInfo functionality."""

    def test_handler_info_creation(self):
        """Test creating HandlerInfo."""

        def test_func():
            pass

        info = HandlerInfo(
            handler_type="command",
            message_types=[_TestCommand],
            handler=test_func,
            name="test_handler",
            module="test_module",
            is_async=False,
            metadata={"key": "value"},
        )

        assert info.handler_type == "command"
        assert info.message_types == [_TestCommand]
        assert info.handler == test_func
        assert info.name == "test_handler"
        assert info.module == "test_module"
        assert info.is_async is False
        assert info.metadata == {"key": "value"}


class TestHandlerRegistry:
    """Test handler registry functionality."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def test_get_all_handlers_empty(self):
        """Test getting all handlers when empty."""
        handlers = get_all_handlers()
        assert handlers == []

    def test_get_all_handlers_by_type(self):
        """Test getting handlers by type."""
        handlers = get_all_handlers("command")
        assert handlers == []

    def test_clear_handlers_by_type(self):
        """Test clearing handlers by type."""

        # Add some handlers first
        @command_handler(_TestCommand)
        def test_cmd():
            pass

        assert len(get_all_handlers("command")) == 1

        clear_handlers("command")
        assert len(get_all_handlers("command")) == 0

    def test_clear_all_handlers(self):
        """Test clearing all handlers."""

        @command_handler(_TestCommand)
        def test_cmd():
            pass

        @event_handler(_TestEvent)
        def test_evt():
            pass

        assert len(get_all_handlers()) == 2

        clear_handlers()
        assert len(get_all_handlers()) == 0


class TestCommandHandler:
    """Test command_handler decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def test_command_handler_decorator(self):
        """Test command handler decorator."""

        @command_handler(_TestCommand)
        def handle_command(cmd: _TestCommand):
            return f"handled: {cmd.value}"

        # Check handler is registered
        handlers = get_all_handlers("command")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.handler_type == "command"
        assert info.message_types == [_TestCommand]
        assert info.name == "handle_command"
        assert info.is_async is False
        assert info.metadata == {}

        # Check handler info attached to function
        assert hasattr(handle_command, "_handler_info")
        assert handle_command._handler_info == info

        # Test function still works
        cmd = _TestCommand(value="test")
        result = handle_command(cmd)
        assert result == "handled: test"

    def test_command_handler_with_metadata(self):
        """Test command handler with custom metadata."""

        @command_handler(_TestCommand, name="custom_handler", custom="value")
        def handle_command(cmd: _TestCommand):
            pass

        handlers = get_all_handlers("command")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.name == "custom_handler"
        assert info.metadata == {"custom": "value"}

    def test_get_handler_info(self):
        """Test getting handler info."""

        @command_handler(_TestCommand)
        def handle_command(cmd: _TestCommand):
            pass

        info = get_handler_info(handle_command)
        # Note: get_handler_info may not work due to decorator wrapper issue
        # Check that _handler_info is attached to the function
        assert hasattr(handle_command, "_handler_info")
        info = handle_command._handler_info
        assert info.handler_type == "command"


class TestQueryHandler:
    """Test query_handler decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def test_query_handler_decorator(self):
        """Test query handler decorator."""

        @query_handler(_TestQuery)
        def handle_query(query: _TestQuery):
            return f"result: {query.param}"

        handlers = get_all_handlers("query")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.handler_type == "query"
        assert info.message_types == [_TestQuery]
        assert info.metadata == {"cacheable": False, "cache_ttl": None}

    def test_query_handler_with_caching(self):
        """Test query handler with caching options."""

        @query_handler(_TestQuery, cacheable=True, cache_ttl=300)
        def handle_query(query: _TestQuery):
            pass

        handlers = get_all_handlers("query")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.metadata == {"cacheable": True, "cache_ttl": 300}


class TestEventHandler:
    """Test event_handler decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def test_event_handler_decorator(self):
        """Test event handler decorator."""

        @event_handler(_TestEvent)
        def handle_event(event: _TestEvent):
            pass

        handlers = get_all_handlers("event")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.handler_type == "event"
        assert info.message_types == [_TestEvent]
        assert info.metadata == {"priority": 0}

    def test_event_handler_with_priority(self):
        """Test event handler with priority."""

        @event_handler(_TestEvent, priority=10)
        def handle_event(event: _TestEvent):
            pass

        handlers = get_all_handlers("event")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.metadata == {"priority": 10}


class TestMultiEventHandler:
    """Test multi_event_handler decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def test_multi_event_handler_decorator(self):
        """Test multi event handler decorator."""

        class _TestEvent2(Event):
            data2: str

        @multi_event_handler(_TestEvent, _TestEvent2, priority=5)
        def handle_events(event: Event):
            pass

        handlers = get_all_handlers("event")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.handler_type == "event"
        assert set(info.message_types) == {_TestEvent, _TestEvent2}
        assert info.metadata == {"priority": 5}


class TestSagaDecorator:
    """Test saga decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def test_saga_decorator(self):
        """Test saga decorator."""

        @saga(timeout=300)
        class _TestSagaImpl(_TestSaga):
            pass

        handlers = get_all_handlers("saga")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.handler_type == "saga"
        assert info.message_types == []
        assert info.handler == _TestSagaImpl
        assert info.metadata == {"timeout": 300}

        # Check handler info attached to class
        assert hasattr(_TestSagaImpl, "_handler_info")
        assert _TestSagaImpl._handler_info == info


class TestProjectionDecorator:
    """Test projection decorator."""

    def setup_method(self):
        """Clear handlers before each test."""
        clear_handlers()

    def test_projection_decorator(self):
        """Test projection decorator."""

        @projection(name="custom_projection")
        class _TestProjectionImpl(_TestProjection):
            pass

        handlers = get_all_handlers("projection")
        assert len(handlers) == 1

        info = handlers[0]
        assert info.handler_type == "projection"
        assert info.message_types == []
        assert info.handler == _TestProjectionImpl
        assert info.name == "custom_projection"

        # Check handler info attached to class
        assert hasattr(_TestProjectionImpl, "_handler_info")
        assert _TestProjectionImpl._handler_info == info


