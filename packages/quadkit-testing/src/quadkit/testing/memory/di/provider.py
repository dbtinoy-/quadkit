from __future__ import annotations

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.events import (
    CommandBusProtocol as CommandBusProtocol,
)
from quadkit.contracts.events import (
    DomainEventPublisherProtocol as DomainEventPublisherProtocol,
)
from quadkit.contracts.events import (
    EventBusProtocol as EventBusProtocol,
)
from quadkit.contracts.events import (
    QueryBusProtocol as QueryBusProtocol,
)
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.testing.memory.cqrs import InMemoryCommandBus, InMemoryQueryBus
from quadkit.testing.memory.event_bus import InMemoryEventBus


class MemoryProvider(Provider):
    """Registers all in-memory bus implementations as singletons."""

    name = "memory"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register InMemoryEventBus, InMemoryCommandBus, InMemoryQueryBus, and AuditLogger."""
        from quadkit.contracts.audit import AuditLoggerProtocol
        from quadkit.testing.memory.audit import InMemoryAuditLogger

        event_bus = InMemoryEventBus()
        container.singleton(EventBusProtocol, instance=event_bus)
        container.singleton(DomainEventPublisherProtocol, instance=event_bus)

        container.singleton(CommandBusProtocol, instance=InMemoryCommandBus())
        container.singleton(QueryBusProtocol, instance=InMemoryQueryBus())
        container.singleton(AuditLoggerProtocol, instance=InMemoryAuditLogger())

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """No boot-time work required for the event bus module."""

    async def shutdown(self) -> None:
        """No resources to release for the event bus module."""


__all__ = ["MemoryProvider"]
