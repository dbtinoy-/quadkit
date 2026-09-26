"""Root hook payload surface for quadkit-events.

Defines canonical payload dataclasses for event-bus/event-store hook points.
Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "EventHandledHook",
    "EventPublishedHook",
    "EventStoredHook",
]


@dataclass(frozen=True, kw_only=True)
class EventPublishedHook:
    """Payload fired when an event is published onto the event bus.

    Attributes:
        event_type: Fully-qualified type name of the published event.
        aggregate_id: Identifier of the aggregate that emitted the event, if known.
    """

    event_type: str
    aggregate_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class EventHandledHook:
    """Payload fired after an event handler successfully processes an event.

    Attributes:
        event_type: Fully-qualified type name of the handled event.
        handler: Qualified name of the handler class or function.
    """

    event_type: str
    handler: str


@dataclass(frozen=True, kw_only=True)
class EventStoredHook:
    """Payload fired when an event is persisted to the event store.

    Attributes:
        event_type: Fully-qualified type name of the stored event.
        stream_id: Identifier of the event stream the event was written to.
    """

    event_type: str
    stream_id: str
