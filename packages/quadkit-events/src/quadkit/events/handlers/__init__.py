"""Handlers module for CQRS message handling.

This module provides:
- Handler base classes
- Handler registry for automatic discovery
- Decorators for handler registration
- Event type discovery utilities
"""

from __future__ import annotations

from quadkit.events.handlers.base import (
    CommandHandlerProtocol,
    EventHandlerProtocol,
    MultiEventHandlerProtocol,
    QueryHandlerProtocol,
)
from quadkit.events.handlers.discovery import (
    discover_and_register,
    discover_event_types,
    register_discovered_types,
)
from quadkit.events.handlers.registry import (
    HandlerRegistry,
    clear_handler_registry,
)

__all__ = [
    "CommandHandlerProtocol",
    "EventHandlerProtocol",
    "HandlerRegistry",
    "MultiEventHandlerProtocol",
    "QueryHandlerProtocol",
    "clear_handler_registry",
    "discover_and_register",
    "discover_event_types",
    "register_discovered_types",
]
