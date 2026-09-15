"""Event sourcing protocol class definitions (CQRS/ES).

Protocols for event buses, command buses, event stores,
and related patterns.
"""

from __future__ import annotations

from quadkit.contracts.events.protocols.cqrs import (
    CommandBusProtocol as CommandBusProtocol,
)
from quadkit.contracts.events.protocols.cqrs import (
    CommandHandlerProtocol as CommandHandlerProtocol,
)
from quadkit.contracts.events.protocols.cqrs import (
    QueryBusProtocol as QueryBusProtocol,
)
from quadkit.contracts.events.protocols.cqrs import (
    QueryHandlerProtocol as QueryHandlerProtocol,
)
from quadkit.contracts.events.protocols.domain import (
    DomainEventPublisherProtocol as DomainEventPublisherProtocol,
)
from quadkit.contracts.events.protocols.domain import (
    EventBusDiagnosticsProtocol as EventBusDiagnosticsProtocol,
)
from quadkit.contracts.events.protocols.domain import (
    EventBusProtocol as EventBusProtocol,
)
from quadkit.contracts.events.protocols.domain import (
    EventHandlerProtocol as EventHandlerProtocol,
)
from quadkit.contracts.events.protocols.domain import (
    EventMiddlewareProtocol as EventMiddlewareProtocol,
)
from quadkit.contracts.events.protocols.domain import (
    MultiEventHandlerProtocol as MultiEventHandlerProtocol,
)
from quadkit.contracts.events.protocols.projection import (
    IntegrationEventProtocol as IntegrationEventProtocol,
)
from quadkit.contracts.events.protocols.projection import (
    ProjectionProtocol as ProjectionProtocol,
)
from quadkit.contracts.events.protocols.projection import (
    PubSubProtocol as PubSubProtocol,
)
from quadkit.contracts.events.protocols.projection import (
    WebhookSignatureVerifierProtocol as WebhookSignatureVerifierProtocol,
)
from quadkit.contracts.events.protocols.store import (
    AggregateFactoryProtocol as AggregateFactoryProtocol,
)
from quadkit.contracts.events.protocols.store import (
    EventReplayProtocol as EventReplayProtocol,
)
from quadkit.contracts.events.protocols.store import (
    EventSourcedReadRepositoryProtocol as EventSourcedReadRepositoryProtocol,
)
from quadkit.contracts.events.protocols.store import (
    EventSourcedRepositoryProtocol as EventSourcedRepositoryProtocol,
)
from quadkit.contracts.events.protocols.store import (
    EventStoreProtocol as EventStoreProtocol,
)
from quadkit.contracts.events.protocols.store import (
    SnapshotStoreProtocol as SnapshotStoreProtocol,
)

__all__ = [
    "AggregateFactoryProtocol",
    "CommandBusProtocol",
    "CommandHandlerProtocol",
    "DomainEventPublisherProtocol",
    "EventBusDiagnosticsProtocol",
    "EventBusProtocol",
    "EventHandlerProtocol",
    "EventMiddlewareProtocol",
    "EventReplayProtocol",
    "EventSourcedReadRepositoryProtocol",
    "EventSourcedRepositoryProtocol",
    "EventStoreProtocol",
    "IntegrationEventProtocol",
    "MultiEventHandlerProtocol",
    "ProjectionProtocol",
    "PubSubProtocol",
    "QueryBusProtocol",
    "QueryHandlerProtocol",
    "SnapshotStoreProtocol",
    "WebhookSignatureVerifierProtocol",
]
