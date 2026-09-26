"""Streaming module for event distribution.

This module provides:
- StreamDispatcher: Dispatch events to subscribers
- EventSubscriber: Subscribe to event streams
- EventFilter: Filter events by various criteria
- EventWebSocketEndpoint: ASGI WebSocket endpoint for streaming events to clients
"""

from __future__ import annotations

from quadkit.events.streaming.dispatcher import StreamDispatcher
from quadkit.events.streaming.filters import (
    CompositeFilter,
    EventFilter,
    FilterBuilder,
    NegatedFilter,
    aggregate_filter,
    metadata_filter,
    time_range_filter,
    type_filter,
)
from quadkit.events.streaming.subscriber import EventSubscriber, Subscription
from quadkit.events.streaming.websocket import EventWebSocketEndpoint

__all__ = [
    "CompositeFilter",
    "EventFilter",
    "EventSubscriber",
    "EventWebSocketEndpoint",
    "FilterBuilder",
    "NegatedFilter",
    "StreamDispatcher",
    "Subscription",
    "aggregate_filter",
    "metadata_filter",
    "time_range_filter",
    "type_filter",
]
