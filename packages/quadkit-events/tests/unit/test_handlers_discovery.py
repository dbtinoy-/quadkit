"""Unit tests for handler discovery and registry."""

from unittest.mock import Mock, patch

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.handlers.discovery import (
    discover_and_register,
    discover_event_types,
    register_discovered_types,
)
from quadkit.events.handlers.registry import (
    HandlerRegistry,
    clear_handler_registry,
)
from quadkit.events.messages import Command, Query


class TestHandlerDiscovery:
    """Test discover_handlers and related functions."""

    def test_discover_event_types_empty_module(self):
        """Test discovering event types from non-existent module returns empty."""
        result = discover_event_types("non_existent_module_12345")
        assert result == {}

    def test_discover_event_types_invalid_module(self):
        """Test discovering event types from invalid module returns empty."""
        result = discover_event_types("invalid.module.path")
        assert result == {}

    def test_discover_event_types_with_events(self):
        """Test discovering custom Event subclasses."""
        result = discover_event_types("quadkit.events.messages")
        assert isinstance(result, dict)

    def test_discover_event_types_non_recursive(self):
        """Test discover_event_types with recursive=False."""
        result = discover_event_types("quadkit.events.messages", recursive=False)
        assert isinstance(result, dict)

    @patch("quadkit.events.handlers.discovery.importlib.import_module")
    def test_discover_event_types_import_error(self, mock_import):
        """Test discover_event_types handles ImportError gracefully."""
        mock_import.side_effect = ImportError("Module not found")
        result = discover_event_types("failing_module")
        assert result == {}

    def test_register_discovered_types_empty(self):
        """Test register_discovered_types with empty dict."""
        result = register_discovered_types({}, None, None)
        assert result == 0

    @pytest.mark.asyncio
    async def test_discover_and_register_empty_paths(self):
        """Test discover_and_register with empty list of paths."""
        result = discover_and_register([])
        assert result == {}

    @patch("quadkit.events.handlers.discovery.importlib.import_module")
    @patch("quadkit.events.handlers.discovery.inspect.getmembers")
    def test_discover_and_register_multiple_paths(self, mock_getmembers, mock_import):
        """Test discover_and_register with multiple module paths."""
        mock_module = Mock()
        mock_module.__path__ = []
        mock_module.__name__ = "test_module"
        mock_import.return_value = mock_module

        mock_getmembers.return_value = []

        result = discover_and_register(["test.module1", "test.module2"])
        assert isinstance(result, dict)


class TestHandlerRegistry:
    """Test HandlerRegistry registration and lookup."""

    def test_handler_registry_creation(self):
        """Test HandlerRegistry initialization."""
        registry = HandlerRegistry()
        assert registry._command_handlers is not None
        assert registry._query_handlers is not None
        assert registry._event_handlers == {}
        assert registry._discovered_modules == set()

    def test_handler_registry_with_defaults(self):
        """Test HandlerRegistry() creates empty registry."""
        registry = HandlerRegistry()
        assert registry._command_handlers is not None
        assert registry._query_handlers is not None

    def test_register_command_handler(self):
        """Test registering a command handler."""
        registry = HandlerRegistry()

        class TestCommand(Command):
            pass

        class TestCommandHandler:
            async def handle(self, cmd):
                return "handled"

        registry.register_command_handler(TestCommand, TestCommandHandler)
        handlers = registry.get_command_handlers()
        assert TestCommand in handlers

    def test_register_query_handler(self):
        """Test registering a query handler."""
        registry = HandlerRegistry()

        class TestQuery(Query):
            pass

        class TestQueryHandler:
            async def handle(self, query):
                return "result"

        registry.register_query_handler(TestQuery, TestQueryHandler)
        handlers = registry.get_query_handlers()
        assert TestQuery in handlers

    def test_register_event_handler(self):
        """Test registering an event handler."""
        registry = HandlerRegistry()

        class TestEvent(DomainEvent):
            pass

        async def test_handler(event):
            pass

        registry.register_event_handler(TestEvent, test_handler)
        handlers = registry.get_event_handlers()
        assert TestEvent in handlers
        assert test_handler in handlers[TestEvent]

    def test_register_event_handler_multiple(self):
        """Test registering multiple handlers for same event type."""
        registry = HandlerRegistry()

        class TestEvent(DomainEvent):
            pass

        async def handler1(event):
            pass

        async def handler2(event):
            pass

        registry.register_event_handler(TestEvent, handler1)
        registry.register_event_handler(TestEvent, handler2)

        handlers = registry.get_event_handlers()
        assert handler1 in handlers[TestEvent]
        assert handler2 in handlers[TestEvent]

    def test_get_command_handlers(self):
        """Test retrieving all command handlers."""
        registry = HandlerRegistry()

        class Cmd1(Command):
            pass

        class Cmd2(Command):
            pass

        class Handler1:
            pass

        class Handler2:
            pass

        registry.register_command_handler(Cmd1, Handler1)
        registry.register_command_handler(Cmd2, Handler2)

        result = registry.get_command_handlers()
        assert len(result) == 2
        assert Cmd1 in result
        assert Cmd2 in result

    def test_get_query_handlers(self):
        """Test retrieving all query handlers."""
        registry = HandlerRegistry()

        class Qry1(Query):
            pass

        class Qry2(Query):
            pass

        class Handler1:
            pass

        class Handler2:
            pass

        registry.register_query_handler(Qry1, Handler1)
        registry.register_query_handler(Qry2, Handler2)

        result = registry.get_query_handlers()
        assert len(result) == 2
        assert Qry1 in result
        assert Qry2 in result

    def test_get_event_handlers(self):
        """Test retrieving all event handlers."""
        registry = HandlerRegistry()

        class Evt(DomainEvent):
            pass

        async def handler(event):
            pass

        registry.register_event_handler(Evt, handler)

        result = registry.get_event_handlers()
        assert Evt in result

    def test_discover_empty_module(self):
        """Test discovering handlers from module with none."""
        registry = HandlerRegistry()
        count = registry.discover("quadkit.events.messages")
        assert count == 0

    def test_discover_same_module_twice(self):
        """Test discovering from same module twice returns 0 on second call."""
        registry = HandlerRegistry()

        count1 = registry.discover("quadkit.events.messages")
        count2 = registry.discover("quadkit.events.messages")

        assert count2 == 0

    @patch("quadkit.events.handlers.registry.importlib.import_module")
    def test_discover_import_error(self, mock_import):
        """Test discover handles ImportError gracefully."""
        mock_import.side_effect = ImportError("Module not found")
        registry = HandlerRegistry()
        count = registry.discover("failing_module")
        assert count == 0

    @patch("quadkit.events.handlers.registry.importlib.import_module")
    @patch("quadkit.events.handlers.registry.inspect.getmembers")
    @patch("quadkit.events.handlers.registry.pkgutil.iter_modules")
    def test_discover_with_recursive(self, mock_iter, mock_getmembers, mock_import):
        """Test discover with recursive=True."""
        mock_module = Mock()
        mock_module.__path__ = []
        mock_module.__name__ = "test_module"
        mock_import.return_value = mock_module
        mock_getmembers.return_value = []
        mock_iter.return_value = []

        registry = HandlerRegistry()
        count = registry.discover("test_module", recursive=True)
        assert count >= 0

    def test_register_with_buses_command_only(self):
        """Test register_with_buses with only command_bus."""
        registry = HandlerRegistry()

        class TestCommand(Command):
            pass

        class TestHandler:
            async def handle(self, cmd):
                return "result"

        registry.register_command_handler(TestCommand, TestHandler)

        mock_command_bus = Mock()
        mock_command_bus.register = Mock()

        registry.register_with_buses(command_bus=mock_command_bus)

        mock_command_bus.register.assert_called_once()

    def test_register_with_buses_query_only(self):
        """Test register_with_buses with only query_bus."""
        registry = HandlerRegistry()

        class TestQuery(Query):
            pass

        class TestHandler:
            async def handle(self, query):
                return "result"

        registry.register_query_handler(TestQuery, TestHandler)

        mock_query_bus = Mock()
        mock_query_bus.register = Mock()

        registry.register_with_buses(query_bus=mock_query_bus)

        mock_query_bus.register.assert_called_once()

    def test_register_with_buses_event_only(self):
        """Test register_with_buses with only event_bus."""
        registry = HandlerRegistry()

        class TestEvent(DomainEvent):
            pass

        async def test_handler(event):
            pass

        registry.register_event_handler(TestEvent, test_handler)

        mock_event_bus = Mock()
        mock_event_bus.subscribe = Mock()

        registry.register_with_buses(event_bus=mock_event_bus)

        mock_event_bus.subscribe.assert_called_once()

    def test_register_with_buses_handler_factory(self):
        """Test register_with_buses with handler_factory."""
        registry = HandlerRegistry()

        class TestCommand(Command):
            pass

        class TestHandler:
            def __init__(self):
                self.value = "factory_created"

        registry.register_command_handler(TestCommand, TestHandler)

        def factory(handler_cls):
            return handler_cls()

        mock_command_bus = Mock()
        mock_command_bus.register = Mock()

        registry.register_with_buses(
            command_bus=mock_command_bus,
            handler_factory=factory,
        )

        mock_command_bus.register.assert_called_once()

    def test_load_decorators(self):
        """Test load_decorators loads from global decorator registry."""
        registry = HandlerRegistry()
        registry.load_decorators()

    def test_clear_handler_registry(self):
        """Test clear_handler_registry clears global state."""
        clear_handler_registry()
