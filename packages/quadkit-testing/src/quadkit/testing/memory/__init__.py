"""In-memory implementations for Quadkit Framework testing.

Provides in-memory implementations of core framework contracts for use in
unit tests, integration tests, and local development. These implementations
are lightweight, fast, and require no external infrastructure.

Exports:
    InMemoryRepository: Generic in-memory data repository.
    InMemoryEventBus: Single-process event dispatch.
    InMemoryCommandBus, InMemoryQueryBus: CQRS buses.
    InMemoryUnitOfWork: Entity tracking and event collection.
    InMemoryAuditLogger: In-memory audit logging.
    InMemoryDistributedLock: Cross-coroutine distributed lock.
    InMemoryAsyncLock: In-process asyncio mutual-exclusion lock.
    InMemoryOutbox, OutboxRelay, OutboxEntry, OutboxStatus: Outbox pattern.
    CommandBusError, CommandHandlerNotFoundError, DuplicateHandlerError,
    QueryBusError, QueryDuplicateHandlerError, QueryHandlerNotFoundError: Errors.
    MemoryProvider: DI provider for in-memory implementations.
    MemoryConfig: Configuration model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.testing.memory.audit import InMemoryAuditLogger
    from quadkit.testing.memory.blob_store import FileInfo, InMemoryBlobStore
    from quadkit.testing.memory.cache import InMemoryCacheBackend
    from quadkit.testing.memory.cqrs import (
        InMemoryCommandBus,
        InMemoryQueryBus,
    )
    from quadkit.testing.memory.event_bus import InMemoryEventBus
    from quadkit.testing.memory.exceptions import (
        CommandBusError,
        CommandError,
        CommandHandlerNotFoundError,
        DuplicateHandlerError,
        QueryBusError,
        QueryDuplicateHandlerError,
        QueryHandlerNotFoundError,
    )
    from quadkit.testing.memory.lock import (
        InMemoryAsyncLock,
        InMemoryDistributedLock,
        InMemoryLockStore,
    )
    from quadkit.testing.memory.notification import InMemoryNotificationChannel
    from quadkit.testing.memory.outbox import (
        InMemoryOutbox,
        OutboxEntry,
        OutboxRelay,
        OutboxStatus,
    )
    from quadkit.testing.memory.queue import InMemoryQueueBackend
    from quadkit.testing.memory.repository import InMemoryRepository
    from quadkit.testing.memory.search import InMemorySearchEngine, SearchResults
    from quadkit.testing.memory.uow import InMemoryUnitOfWork

_LAZY_IMPORTS: dict[str, str] = {
    "InMemoryBlobStore": "quadkit.testing.memory.blob_store",
    "FileInfo": "quadkit.testing.memory.blob_store",
    "InMemoryCacheBackend": "quadkit.testing.memory.cache",
    "InMemoryAuditLogger": "quadkit.testing.memory.audit",
    "CommandBusError": "quadkit.testing.memory.exceptions",
    "CommandError": "quadkit.testing.memory.exceptions",
    "CommandHandlerNotFoundError": "quadkit.testing.memory.exceptions",
    "DuplicateHandlerError": "quadkit.testing.memory.exceptions",
    "InMemoryCommandBus": "quadkit.testing.memory.cqrs",
    "InMemoryQueryBus": "quadkit.testing.memory.cqrs",
    "QueryBusError": "quadkit.testing.memory.exceptions",
    "QueryDuplicateHandlerError": "quadkit.testing.memory.exceptions",
    "QueryHandlerNotFoundError": "quadkit.testing.memory.exceptions",
    "InMemoryEventBus": "quadkit.testing.memory.event_bus",
    "InMemoryAsyncLock": "quadkit.testing.memory.lock",
    "InMemoryDistributedLock": "quadkit.testing.memory.lock",
    "InMemoryLockStore": "quadkit.testing.memory.lock",
    "InMemoryOutbox": "quadkit.testing.memory.outbox",
    "OutboxEntry": "quadkit.testing.memory.outbox",
    "OutboxRelay": "quadkit.testing.memory.outbox",
    "OutboxStatus": "quadkit.testing.memory.outbox",
    "InMemoryRepository": "quadkit.testing.memory.repository",
    "InMemoryNotificationChannel": "quadkit.testing.memory.notification",
    "InMemoryQueueBackend": "quadkit.testing.memory.queue",
    "InMemorySearchEngine": "quadkit.testing.memory.search",
    "SearchResults": "quadkit.testing.memory.search",
    "InMemoryUnitOfWork": "quadkit.testing.memory.uow",
    "MemoryConfig": "quadkit.testing.memory.config.models",
    "MemoryBackendError": "quadkit.testing.memory.exceptions",
    "MemoryProvider": "quadkit.testing.memory.di.provider",
    "DEFAULT_AUDIT_CAPACITY": "quadkit.testing.memory.constants",
    "DEFAULT_EVENT_BUS_CAPACITY": "quadkit.testing.memory.constants",
    "DEFAULT_OUTBOX_CAPACITY": "quadkit.testing.memory.constants",
    "DEFAULT_REPOSITORY_CAPACITY": "quadkit.testing.memory.constants",
}


def __getattr__(name: str) -> object:
    """Lazily import and return a public attribute by name."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """Return list of public API names."""
    return list(_LAZY_IMPORTS.keys())


__all__ = list(_LAZY_IMPORTS.keys())
