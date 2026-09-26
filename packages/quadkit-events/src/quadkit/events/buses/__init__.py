"""Buses module for Event Sourcing and CQRS.

This module provides the message bus implementations:
- CommandBusImpl: For dispatching commands (single handler)
- QueryBusImpl: For dispatching queries (single handler)
- EventBusImpl: For publishing events (multiple handlers)
"""

from __future__ import annotations

from quadkit.events.buses.base import Bus, MiddlewareFunc
from quadkit.events.buses.command import CommandBusImpl
from quadkit.events.buses.event import EventBusImpl
from quadkit.events.buses.query import QueryBusImpl

__all__ = [
    "Bus",
    "CommandBusImpl",
    "EventBusImpl",
    "MiddlewareFunc",
    "QueryBusImpl",
]
