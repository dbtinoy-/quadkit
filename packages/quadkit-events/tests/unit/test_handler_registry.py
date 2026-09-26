"""Tests for events handler registry module."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from quadkit.events.handlers.registry import HandlerRegistry
from quadkit.events.handlers.base import CommandHandlerProtocol, EventHandlerProtocol, QueryHandlerProtocol


class TestHandlerRegistry:
    def test_registry_initialization(self) -> None:
        registry = HandlerRegistry()
        assert registry.get_command_handlers() == {}
        assert registry.get_query_handlers() == {}
        assert registry.get_event_handlers() == {}

    def test_register_command_handler(self) -> None:
        registry = HandlerRegistry()

        class FakeCommand:
            pass

        class FakeHandler:
            pass

        registry.register_command_handler(FakeCommand, FakeHandler)
        handlers = registry.get_command_handlers()
        assert FakeCommand in handlers
        assert handlers[FakeCommand] is FakeHandler

    def test_register_query_handler(self) -> None:
        registry = HandlerRegistry()

        class FakeQuery:
            pass

        class FakeHandler:
            pass

        registry.register_query_handler(FakeQuery, FakeHandler)
        handlers = registry.get_query_handlers()
        assert FakeQuery in handlers
        assert handlers[FakeQuery] is FakeHandler

    def test_register_event_handler(self) -> None:
        registry = HandlerRegistry()

        class FakeEvent:
            pass

        class FakeHandler:
            pass

        registry.register_event_handler(FakeEvent, FakeHandler)
        handlers = registry.get_event_handlers()
        assert FakeEvent in handlers
        assert len(handlers[FakeEvent]) == 1

    def test_register_multiple_event_handlers(self) -> None:
        registry = HandlerRegistry()

        class FakeEvent:
            pass

        class FakeHandler1:
            pass

        class FakeHandler2:
            pass

        registry.register_event_handler(FakeEvent, FakeHandler1)
        registry.register_event_handler(FakeEvent, FakeHandler2)
        handlers = registry.get_event_handlers()
        assert len(handlers[FakeEvent]) == 2

    def test_discover_returns_zero_for_nonexistent_module(self) -> None:
        registry = HandlerRegistry()
        count = registry.discover("nonexistent.module.path")
        assert count == 0

    def test_discover_returns_zero_for_already_discovered(self) -> None:
        registry = HandlerRegistry()
        registry._discovered_modules.add("some.module")
        count = registry.discover("some.module")
        assert count == 0

    def test_get_command_handlers_returns_copy(self) -> None:
        registry = HandlerRegistry()

        class FakeCommand:
            pass

        class FakeHandler:
            pass

        registry.register_command_handler(FakeCommand, FakeHandler)
        handlers = registry.get_command_handlers()
        handlers[FakeCommand] = "modified"
        assert registry.get_command_handlers()[FakeCommand] is FakeHandler

    def test_get_query_handlers_returns_copy(self) -> None:
        registry = HandlerRegistry()

        class FakeQuery:
            pass

        class FakeHandler:
            pass

        registry.register_query_handler(FakeQuery, FakeHandler)
        handlers = registry.get_query_handlers()
        handlers[FakeQuery] = "modified"
        assert registry.get_query_handlers()[FakeQuery] is FakeHandler

    def test_get_event_handlers_returns_copy(self) -> None:
        registry = HandlerRegistry()

        class FakeEvent:
            pass

        class FakeHandler:
            pass

        registry.register_event_handler(FakeEvent, FakeHandler)
        handlers = registry.get_event_handlers()
        handlers[FakeEvent].clear()
        assert len(registry.get_event_handlers()[FakeEvent]) == 1
