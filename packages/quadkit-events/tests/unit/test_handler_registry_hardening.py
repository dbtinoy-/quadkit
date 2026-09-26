"""Tests for HandlerRegistry hardening features.

Tests the with_defaults() classmethod and clear_handler_registry() function
added in ev-25.
"""

from __future__ import annotations

import pytest

from quadkit.events.decorators.handlers import (
    _handler_registry,
    clear_handlers,
    command_handler,
    event_handler,
)
from quadkit.events.handlers.registry import (
    HandlerRegistry,
    clear_handler_registry,
)
from quadkit.events.messages.command import Command
from quadkit.events.messages.event import Event


class SampleCommand(Command):
    """Sample command for testing."""

    pass


class SampleEvent(Event):
    """Sample event for testing."""

    pass


class TestHandlerRegistryWithDefaults:
    """Tests for HandlerRegistry() classmethod."""

    def test_with_defaults_returns_handler_registry(self) -> None:
        """with_defaults() should return a HandlerRegistry instance."""
        registry = HandlerRegistry()
        assert isinstance(registry, HandlerRegistry)

    def test_with_defaults_creates_fresh_instance(self) -> None:
        """with_defaults() should create separate instances."""
        r1 = HandlerRegistry()
        r2 = HandlerRegistry()
        assert r1 is not r2

    def test_with_defaults_creates_empty_registry(self) -> None:
        """with_defaults() should create a registry with no handlers."""
        registry = HandlerRegistry()
        assert registry.get_command_handlers() == {}
        assert registry.get_query_handlers() == {}
        assert registry.get_event_handlers() == {}

    def test_with_defaults_registry_can_register_handlers(self) -> None:
        """Registries from with_defaults() should accept handler registration."""
        registry = HandlerRegistry()

        def dummy_handler(cmd: SampleCommand) -> None:
            pass

        registry.register_command_handler(SampleCommand, dummy_handler)
        assert SampleCommand in registry.get_command_handlers()


class TestClearHandlerRegistry:
    """Tests for clear_handler_registry() function."""

    def test_clear_handler_registry_is_callable(self) -> None:
        """clear_handler_registry() should be callable without arguments."""
        clear_handler_registry()  # Should not raise

    def test_clear_handler_registry_removes_decorated_handlers(self) -> None:
        """clear_handler_registry() should clear decorated handlers."""
        # Register a handler using decorator
        @command_handler(SampleCommand)
        def my_handler(cmd: SampleCommand) -> None:
            pass

        # Verify it's registered
        from quadkit.events.decorators.handlers import get_all_handlers

        assert len(get_all_handlers("command")) > 0

        # Clear handlers
        clear_handler_registry()

        # Verify it's cleared
        assert len(get_all_handlers("command")) == 0

    def test_clear_handler_registry_clears_all_handler_types(self) -> None:
        """clear_handler_registry() should clear command, query, and event handlers."""
        # Register handlers of different types
        @command_handler(SampleCommand)
        def cmd_handler(cmd: SampleCommand) -> None:
            pass

        @event_handler(SampleEvent)
        def evt_handler(evt: SampleEvent) -> None:
            pass

        # Verify they're registered
        from quadkit.events.decorators.handlers import get_all_handlers

        assert len(get_all_handlers("command")) > 0
        assert len(get_all_handlers("event")) > 0

        # Clear handlers
        clear_handler_registry()

        # Verify all are cleared
        assert len(get_all_handlers("command")) == 0
        assert len(get_all_handlers("query")) == 0
        assert len(get_all_handlers("event")) == 0

    def test_clear_handler_registry_idempotent(self) -> None:
        """clear_handler_registry() should be safe to call multiple times."""
        # Register a handler
        @command_handler(SampleCommand)
        def my_handler(cmd: SampleCommand) -> None:
            pass

        # Clear multiple times
        clear_handler_registry()
        clear_handler_registry()
        clear_handler_registry()

        # Should not raise


class TestClearHandlerRegistryExports:
    """Tests for clear_handler_registry() export locations."""

    def test_clear_handler_registry_importable_from_registry_module(self) -> None:
        """clear_handler_registry should be importable from handlers.registry."""
        from quadkit.events.handlers.registry import (
            clear_handler_registry as cfr,
        )

        assert callable(cfr)

    def test_clear_handler_registry_importable_from_handlers_package(self) -> None:
        """clear_handler_registry should be importable from handlers package."""
        from quadkit.events.handlers import clear_handler_registry as cfr

        assert callable(cfr)

    def test_clear_handler_registry_importable_from_decorators(self) -> None:
        """clear_handler_registry should be importable from decorators module."""
        from quadkit.events.decorators import clear_handler_registry as cfr

        assert callable(cfr)

    def test_clear_handler_registry_importable_from_events(self) -> None:
        """clear_handler_registry should be importable from events package."""
        from quadkit.events import clear_handler_registry as cfr

        assert callable(cfr)


class TestIntegration:
    """Integration tests for handler registry hardening."""

    def test_workflow_register_clear_register(self) -> None:
        """Test typical workflow: register, clear, then register again."""
        from quadkit.events.decorators.handlers import get_all_handlers

        # Clear to start fresh
        clear_handler_registry()

        # Register a command handler
        @command_handler(SampleCommand)
        def cmd_handler(cmd: SampleCommand) -> None:
            pass

        assert len(get_all_handlers("command")) == 1

        # Clear
        clear_handler_registry()
        assert len(get_all_handlers("command")) == 0

        # Register again
        @command_handler(SampleCommand)
        def cmd_handler_2(cmd: SampleCommand) -> None:
            pass

        assert len(get_all_handlers("command")) == 1

    def test_handler_registry_with_defaults_independent(self) -> None:
        """HandlerRegistry() instances should be independent."""
        r1 = HandlerRegistry()
        r2 = HandlerRegistry()

        def handler1(cmd: SampleCommand) -> None:
            pass

        def handler2(cmd: SampleCommand) -> None:
            pass

        r1.register_command_handler(SampleCommand, handler1)
        r2.register_command_handler(SampleCommand, handler2)

        # Each should have its own handler
        assert SampleCommand in r1.get_command_handlers()
        assert SampleCommand in r2.get_command_handlers()
        assert r1.get_command_handlers()[SampleCommand] is handler1
        assert r2.get_command_handlers()[SampleCommand] is handler2
