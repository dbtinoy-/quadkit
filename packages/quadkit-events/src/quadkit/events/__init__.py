"""Quadkit Events - Event Sourcing and CQRS for Python.

This package provides a complete Event Sourcing and CQRS implementation
for building scalable, event-driven applications.

Core Features:
    - **Event Sourcing**: Store all changes as immutable events
    - **CQRS**: Separate read and write models for scalability
    - **Aggregate Pattern**: DDD building blocks for domain modeling
    - **Event Store**: Multiple backends (PostgreSQL, MongoDB, In-Memory)
    - **Sagas**: Long-running business processes
    - **Projections**: Build read models from events
    - **Streaming**: Real-time event streaming with WebSocket support
    - **Middleware**: Extensible middleware pipeline

Basic Usage:
    ```python
    from quadkit.contracts.domain import DomainEvent
    from quadkit.events import (
        Command, Query, Event,
        CommandBusImpl, QueryBusImpl, EventBusImpl,
        AggregateRoot, InMemoryEventStore,
    )

    # Define events
    class UserCreated(DomainEvent):
        user_id: UUID
        name: str
        email: str
    ```

Module Structure:
    - messages: Command, Query, Event base classes
    - buses: CommandBusImpl, QueryBusImpl, EventBusImpl
    - stores: Event storage backends
    - aggregates: AggregateRoot, Entity, ValueObject
    - repository: Event sourcing repository
    - handlers: Handler registration and discovery
    - middleware: Middleware pipeline components
    - projections: Read model management
    - streaming: Event streaming and WebSocket
    - adapters: Message broker adapters (RabbitMQ, Kafka, Azure)
    - schema: Schema registry and evolution
"""

from __future__ import annotations

import importlib.metadata
import sys
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.events.constants import __version__ as __version__

# Lazy loading to avoid circular imports

if TYPE_CHECKING:
    from quadkit.contracts.data import ReadOnlyRepositoryProtocol
    from quadkit.contracts.domain import DomainEvent
    from quadkit.contracts.events import (
        AggregateFactoryProtocol,
        CommandBusProtocol,
        CommandHandlerProtocol,
        DomainEventPublisherProtocol,
        EventBusProtocol,
        EventHandlerProtocol,
        EventStoreProtocol,
        MultiEventHandlerProtocol,
        ProjectionProtocol,
        QueryBusProtocol,
        QueryHandlerProtocol,
        SnapshotStoreProtocol,
    )
    from quadkit.contracts.workflow import (
        SagaManagerProtocol,
        SagaProtocol,
    )
    from quadkit.events.aggregates.aggregate import AggregateRoot
    from quadkit.events.aggregates.entity import Entity
    from quadkit.events.aggregates.value_object import ValueObject
    from quadkit.events.buses.command import CommandBusImpl
    from quadkit.events.buses.event import (
        DispatchResult,
        EventBusImpl,
    )
    from quadkit.events.buses.query import QueryBusImpl
    from quadkit.events.config import (
        CommandBusConfig,
        EventBusConfig,
        EventsConfig,
        InMemoryEventStoreConfig,
        MongoDBEventStoreConfig,
        PostgresEventStoreConfig,
        QueryBusConfig,
        SnapshotConfig,
    )
    from quadkit.events.decorators.handlers import (
        command_handler,
        event_handler,
        query_handler,
    )
    from quadkit.events.di import EventsProvider
    from quadkit.events.exceptions import (
        AggregateNotFoundError,
        ConcurrencyError,
        EventError,
        EventLoadError,
        EventPersistenceError,
        EventStoreConnectionError,
        EventStoreError,
        HandlerNotFoundError,
        ProjectionBuildError,
        ProjectionNotFoundError,
        SchemaError,
        SecurityError,
        StreamingError,
        StreamNotFoundError,
        WebhookDeliveryError,
    )
    from quadkit.events.handlers.registry import (
        HandlerRegistry,
    )
    from quadkit.events.messages.base import (
        Message,
        MessageMetadata,
    )
    from quadkit.events.messages.command import (
        Command,
        IdempotentCommand,
    )
    from quadkit.events.messages.event import (
        Event,
        IntegrationEvent,
    )
    from quadkit.events.messages.query import (
        PagedResult,
        PaginatedQuery,
        Query,
    )
    from quadkit.events.middleware.base import (
        AbstractMiddleware,
        NextHandler,
    )
    from quadkit.events.protocols import (
        EventFilterProtocol,
        EventSerializerProtocol,
    )
    from quadkit.events.repository.base import (
        AbstractReadOnlyRepository,
        AbstractRepository,
    )
    from quadkit.events.repository.event_sourcing import EventSourcingRepository
    from quadkit.events.stores import (
        HAS_MONGODB,
        HAS_POSTGRES,
        HAS_SQLITE,
        PostgresEventStore,
        PostgresSnapshotStore,
    )
    from quadkit.events.stores.base import (
        AbstractEventStore,
        AbstractSnapshotStore,
    )
    from quadkit.events.stores.memory import (
        InMemoryEventStore,
        InMemorySnapshotStore,
    )
    from quadkit.events.stores.redis import RedisEventStore
    from quadkit.events.stores.snapshot import SnapshotManager
    from quadkit.events.types import (
        AggregateStatus,
        Checkpoint,
        CommandResult,
        EventEnvelope,
        EventStoreBackend,
        HandlerInfo,
        MessageType,
        MiddlewareInfo,
        ProjectionState,
        QueryResult,
        Snapshot,
        SnapshotStrategy,
        StreamInfo,
        StreamPosition,
    )
    from quadkit.events.version_skew import (
        KnownEventSetRegistry,
        VersionAwareSubscription,
        known_events,
    )
    from quadkit.events.webhooks.dispatcher import (
        WebhookDispatcher,
        WebhookEndpoint,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # Module
    "EventsModule": ("quadkit.events.module", "EventsModule"),
    # Buses (concrete implementations — primary names for test/runtime use)
    "CommandBusProtocol": ("quadkit.contracts.events", "CommandBusProtocol"),
    "CommandBusImpl": ("quadkit.events.buses.command", "CommandBusImpl"),
    "CommandBus": ("quadkit.contracts", "CommandBusProtocol"),
    "EventBusProtocol": ("quadkit.contracts.events", "EventBusProtocol"),
    "EventBusImpl": ("quadkit.events.buses.event", "EventBusImpl"),
    "EventBus": ("quadkit.contracts", "EventBusProtocol"),
    "QueryBusProtocol": ("quadkit.contracts.events", "QueryBusProtocol"),
    "QueryBusImpl": ("quadkit.events.buses.query", "QueryBusImpl"),
    "QueryBus": ("quadkit.contracts", "QueryBusProtocol"),
    "command_handler": ("quadkit.events.decorators.handlers", "command_handler"),
    "event_handler": ("quadkit.events.decorators.handlers", "event_handler"),
    "query_handler": ("quadkit.events.decorators.handlers", "query_handler"),
    "NextHandler": ("quadkit.events.middleware.base", "NextHandler"),
    "AbstractMiddleware": ("quadkit.events.middleware.base", "AbstractMiddleware"),
    # Config
    "CommandBusConfig": ("quadkit.events.config", "CommandBusConfig"),
    "EventBusConfig": ("quadkit.events.config", "EventBusConfig"),
    "EventsConfig": ("quadkit.events.config", "EventsConfig"),
    "InMemoryEventStoreConfig": ("quadkit.events.config", "InMemoryEventStoreConfig"),
    "MongoDBEventStoreConfig": ("quadkit.events.config", "MongoDBEventStoreConfig"),
    "PostgresEventStoreConfig": ("quadkit.events.config", "PostgresEventStoreConfig"),
    "PostgresEventStore": ("quadkit.events.stores", "PostgresEventStore"),
    "PostgresSnapshotStore": ("quadkit.events.stores", "PostgresSnapshotStore"),
    "RedisEventStore": ("quadkit.events.stores.redis", "RedisEventStore"),
    "QueryBusConfig": ("quadkit.events.config", "QueryBusConfig"),
    "SnapshotConfig": ("quadkit.events.config", "SnapshotConfig"),
    # Exceptions
    "AggregateNotFoundError": ("quadkit.events.exceptions", "AggregateNotFoundError"),
    "CommandExecutionError": ("quadkit.events.exceptions", "CommandExecutionError"),
    "ConcurrencyError": ("quadkit.events.exceptions", "ConcurrencyError"),
    "DuplicateHandlerError": ("quadkit.events.exceptions", "DuplicateHandlerError"),
    "EventError": ("quadkit.events.exceptions", "EventError"),
    "EventLoadError": ("quadkit.events.exceptions", "EventLoadError"),
    "EventPersistenceError": ("quadkit.events.exceptions", "EventPersistenceError"),
    "EventStoreConnectionError": (
        "quadkit.events.exceptions",
        "EventStoreConnectionError",
    ),
    "EventStoreError": ("quadkit.events.exceptions", "EventStoreError"),
    "HandlerNotFoundError": ("quadkit.events.exceptions", "HandlerNotFoundError"),
    "ProjectionBuildError": ("quadkit.events.exceptions", "ProjectionBuildError"),
    "ProjectionNotFoundError": (
        "quadkit.events.exceptions",
        "ProjectionNotFoundError",
    ),
    "QueryExecutionError": ("quadkit.events.exceptions", "QueryExecutionError"),
    "SchemaError": ("quadkit.events.exceptions", "SchemaError"),
    "SecurityError": ("quadkit.events.exceptions", "SecurityError"),
    "StreamingError": ("quadkit.events.exceptions", "StreamingError"),
    "StreamNotFoundError": ("quadkit.events.exceptions", "StreamNotFoundError"),
    "WebhookDeliveryError": ("quadkit.events.exceptions", "WebhookDeliveryError"),
    # Webhooks
    "WebhookDispatcher": ("quadkit.events.webhooks.dispatcher", "WebhookDispatcher"),
    "WebhookEndpoint": ("quadkit.events.webhooks.dispatcher", "WebhookEndpoint"),
    # Messages
    "Command": ("quadkit.events.messages.command", "Command"),
    "Event": ("quadkit.events.messages.event", "Event"),
    # Domain event base from contracts for convenience
    "DomainEvent": ("quadkit.contracts.domain", "DomainEvent"),
    "IdempotentCommand": ("quadkit.events.messages.command", "IdempotentCommand"),
    "IntegrationEvent": ("quadkit.events.messages.event", "IntegrationEvent"),
    "Message": ("quadkit.events.messages.base", "Message"),
    "MessageMetadata": ("quadkit.events.messages.base", "MessageMetadata"),
    "PagedResult": ("quadkit.events.messages.query", "PagedResult"),
    "PaginatedQuery": ("quadkit.events.messages.query", "PaginatedQuery"),
    "Query": ("quadkit.events.messages.query", "Query"),
    # Stores
    "HAS_MONGODB": ("quadkit.events.stores", "HAS_MONGODB"),
    "HAS_POSTGRES": ("quadkit.events.stores", "HAS_POSTGRES"),
    "HAS_SQLITE": ("quadkit.events.stores", "HAS_SQLITE"),
    "AbstractEventStore": ("quadkit.events.stores.base", "AbstractEventStore"),
    "InMemoryEventStore": ("quadkit.events.stores.memory", "InMemoryEventStore"),
    "InMemorySnapshotStore": ("quadkit.events.stores.memory", "InMemorySnapshotStore"),
    "SnapshotManager": ("quadkit.events.stores.snapshot", "SnapshotManager"),
    "AbstractSnapshotStore": ("quadkit.events.stores.base", "AbstractSnapshotStore"),
    # DTOs
    "Checkpoint": ("quadkit.events.types", "Checkpoint"),
    "EventEnvelope": ("quadkit.events.types", "EventEnvelope"),
    "Snapshot": ("quadkit.events.types", "Snapshot"),
    "StreamInfo": ("quadkit.events.types", "StreamInfo"),
    # Enums
    "AggregateStatus": ("quadkit.events.types", "AggregateStatus"),
    "EventStoreBackend": ("quadkit.events.types", "EventStoreBackend"),
    "MessageType": ("quadkit.events.types", "MessageType"),
    "ProjectionState": ("quadkit.events.types", "ProjectionState"),
    "SnapshotStrategy": ("quadkit.events.types", "SnapshotStrategy"),
    "StreamPosition": ("quadkit.events.types", "StreamPosition"),
    # Results
    "CommandResult": ("quadkit.events.types", "CommandResult"),
    "DispatchResult": ("quadkit.events.buses.event", "DispatchResult"),
    "HandlerInfo": ("quadkit.events.types", "HandlerInfo"),
    "MiddlewareInfo": ("quadkit.events.types", "MiddlewareInfo"),
    "QueryResult": ("quadkit.events.types", "QueryResult"),
    # Aggregates
    "AggregateRoot": ("quadkit.events.aggregates.aggregate", "AggregateRoot"),
    "Entity": ("quadkit.events.aggregates.entity", "Entity"),
    "ValueObject": ("quadkit.events.aggregates.value_object", "ValueObject"),
    # Handlers
    "CommandHandlerProtocol": (
        "quadkit.events.handlers.registry",
        "CommandHandlerProtocol",
    ),
    "EventHandlerProtocol": (
        "quadkit.events.handlers.registry",
        "EventHandlerProtocol",
    ),
    "HandlerRegistry": ("quadkit.events.handlers.registry", "HandlerRegistry"),
    "QueryHandlerProtocol": (
        "quadkit.events.handlers.registry",
        "QueryHandlerProtocol",
    ),
    "clear_handler_registry": (
        "quadkit.events.handlers.registry",
        "clear_handler_registry",
    ),
    # RepositoryProtocol
    "EventSourcingRepository": (
        "quadkit.events.repository.event_sourcing",
        "EventSourcingRepository",
    ),
    "RepositoryProtocol": ("quadkit.contracts.data", "RepositoryProtocol"),
    "AbstractRepository": ("quadkit.events.repository.base", "AbstractRepository"),
    "AbstractReadOnlyRepository": (
        "quadkit.events.repository.base",
        "AbstractReadOnlyRepository",
    ),
    # Provider
    "EventsProvider": ("quadkit.events.di", "EventsProvider"),
    # Version skew
    "VersionAwareSubscription": (
        "quadkit.events.version_skew.subscription",
        "VersionAwareSubscription",
    ),
    "KnownEventSetRegistry": (
        "quadkit.events.version_skew.registry",
        "KnownEventSetRegistry",
    ),
    "known_events": (
        "quadkit.events.version_skew.decorator",
        "known_events",
    ),
    # Contracts
    "AggregateFactoryProtocol": (
        "quadkit.contracts.events",
        "AggregateFactoryProtocol",
    ),
    "DomainEventPublisherProtocol": (
        "quadkit.contracts.events",
        "DomainEventPublisherProtocol",
    ),
    "EventStoreProtocol": ("quadkit.contracts.events", "EventStoreProtocol"),
    "MultiEventHandlerProtocol": (
        "quadkit.contracts.events",
        "MultiEventHandlerProtocol",
    ),
    "ProjectionProtocol": ("quadkit.contracts.events", "ProjectionProtocol"),
    "ReadOnlyRepositoryProtocol": (
        "quadkit.contracts.data",
        "ReadOnlyRepositoryProtocol",
    ),
    "SagaProtocol": ("quadkit.contracts.workflow", "SagaProtocol"),
    "SagaManagerProtocol": ("quadkit.contracts.workflow", "SagaManagerProtocol"),
    "SnapshotStoreProtocol": ("quadkit.contracts.events", "SnapshotStoreProtocol"),
    # Optional stores (sqlite, postgres, mongodb — available if extras installed)
    "SqliteConfig": ("quadkit.events.stores.sqlite", "SqliteConfig"),
    "SqliteEventStore": ("quadkit.events.stores.sqlite", "SqliteEventStore"),
    "SqliteSnapshotStore": ("quadkit.events.stores.sqlite", "SqliteSnapshotStore"),
    "MongoDBConfig": ("quadkit.events.stores.mongodb", "MongoDBConfig"),
    "MongoDBEventStore": ("quadkit.events.stores.mongodb", "MongoDBEventStore"),
    "MongoDBSnapshotStore": ("quadkit.events.stores.mongodb", "MongoDBSnapshotStore"),
    # Internal protocols
    "EventSerializerProtocol": ("quadkit.events.protocols", "EventSerializerProtocol"),
    "EventFilterProtocol": ("quadkit.events.protocols", "EventFilterProtocol"),
    # Events (operational meta-events)
    "EventPublishedEvent": ("quadkit.events.events", "EventPublishedEvent"),
    "ProjectionUpdatedEvent": ("quadkit.events.events", "ProjectionUpdatedEvent"),
    # Hooks
    "EventHandledHook": ("quadkit.events.hooks", "EventHandledHook"),
    "EventPublishedHook": ("quadkit.events.hooks", "EventPublishedHook"),
    "EventStoredHook": ("quadkit.events.hooks", "EventStoredHook"),
    # Reactive bridges
    "from_bus": ("quadkit.events.reactive", "from_bus"),
    "from_store": ("quadkit.events.reactive", "from_store"),
    "retry_with_resilience": ("quadkit.events.reactive", "retry_with_resilience"),
}


def __getattr__(name: str) -> Any:
    """Lazy load attributes to avoid circular imports."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """List available attributes for IDE support."""
    return list(__all__) + list(_LAZY_IMPORTS.keys())


__all__ = list(_LAZY_IMPORTS)
