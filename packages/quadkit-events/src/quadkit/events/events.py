"""Root event surface for quadkit-events.

Defines operational meta-events emitted by the event infrastructure itself
(bus publishes, projection updates).  Consumers subscribe via
:class:`~quadkit.contracts.events.protocols.EventBusProtocol`.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "EventPublishedEvent",
    "ProjectionUpdatedEvent",
]


@dataclass(frozen=True, kw_only=True)
class EventPublishedEvent(DomainEvent):
    """Emitted when the event bus successfully publishes a domain event.

    Attributes:
        source_event_type: Fully-qualified type name of the published event.
        handler_count: Number of registered handlers that were notified.
    """

    source_event_type: str
    handler_count: int = 0


@dataclass(frozen=True, kw_only=True)
class ProjectionUpdatedEvent(DomainEvent):
    """Emitted when a read-model projection is rebuilt or updated.

    Attributes:
        projection_name: Canonical name of the projection that was updated.
        events_processed: Number of domain events processed in this update.
    """

    projection_name: str
    events_processed: int = 0
