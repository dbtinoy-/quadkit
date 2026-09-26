"""Tests for events module."""

from __future__ import annotations

import pytest

from quadkit.contracts.events import CommandBusProtocol, EventBusProtocol, QueryBusProtocol
from quadkit.di.module import DynamicModule
from quadkit.events import EventsModule


class TestEventsModule:
    """Test suite for EventsModule."""

    def test_module_decorator_exists(self) -> None:
        """Verify @module decorator is applied to EventsModule."""
        assert hasattr(EventsModule, '__quadkit_module__')

    def test_configure_returns_dynamic_module(self) -> None:
        """Verify configure() returns DynamicModule instance."""
        result = EventsModule.configure()
        assert isinstance(result, DynamicModule)
        assert result.module is EventsModule

    def test_configure_exports_event_protocols(self) -> None:
        """Verify configure() exports CQRS/event protocols."""
        result = EventsModule.configure()
        expected_protocols = [EventBusProtocol, CommandBusProtocol, QueryBusProtocol]
        for protocol in expected_protocols:
            assert protocol in result.exports
