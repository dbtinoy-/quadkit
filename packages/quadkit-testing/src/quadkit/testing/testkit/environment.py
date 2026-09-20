"""TestEnvironment — a pre-wired container for unit tests.

Provides a ready-to-use :class:`TestEnvironment` that registers all
in-memory fakes as singletons so unit tests do not need to manually
wire the container.

Example::

    from quadkit.testing.testkit.environment import TestEnvironment

    async def test_my_service() -> None:
        env = TestEnvironment()
        await env.setup()

        service = MyService(
            event_bus=env.event_bus,
            command_bus=env.command_bus,
        )
        await service.do_something()

        env.teardown()
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.audit import AuditLoggerProtocol
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
from quadkit.di.container import Container
from quadkit.testing.memory.audit import InMemoryAuditLogger
from quadkit.testing.memory.cqrs import InMemoryCommandBus, InMemoryQueryBus
from quadkit.testing.memory.event_bus import InMemoryEventBus
from quadkit.testing.memory.lock import (
    InMemoryDistributedLock,
    InMemoryLockStore,
)
from quadkit.testing.memory.repository import InMemoryRepository
from quadkit.testing.memory.uow import InMemoryUnitOfWork


class TestEnvironment:
    """Pre-wired container environment for unit tests.

    Instantiates all in-memory fakes and registers them as singletons in a
    fresh :class:`~quadkit.di.container.Container`.  Access the fakes
    directly via attributes or resolve them from :attr:`container`.

    Args:
        extra_registrations: Optional callable that accepts the
            :class:`~quadkit.di.container.Container` for additional
            singleton registrations before :meth:`setup` completes.

    Example::

        env = TestEnvironment()
        await env.setup()
        assert env.event_bus is not None
        env.teardown()
    """

    def __init__(
        self,
        extra_registrations: Any = None,
    ) -> None:
        self._extra_registrations = extra_registrations
        self.container: Container = Container()

        # Fakes — populated in setup()
        self.event_bus: InMemoryEventBus
        self.command_bus: InMemoryCommandBus
        self.query_bus: InMemoryQueryBus
        self.audit_logger: InMemoryAuditLogger
        self.lock: InMemoryDistributedLock
        self.lock_store: InMemoryLockStore

    async def setup(self) -> TestEnvironment:
        """Instantiate fakes and register them with the container.

        Returns:
            Self, to allow ``env = await TestEnvironment().setup()``.
        """
        event_bus = InMemoryEventBus()
        command_bus = InMemoryCommandBus()
        query_bus = InMemoryQueryBus()
        audit_logger = InMemoryAuditLogger()
        # One store per environment: every lock this environment hands out
        # coordinates with the others, and nothing leaks into other tests.
        lock_store = InMemoryLockStore()
        lock = InMemoryDistributedLock(store=lock_store)

        self.event_bus = event_bus
        self.command_bus = command_bus
        self.query_bus = query_bus
        self.audit_logger = audit_logger
        self.lock = lock
        self.lock_store = lock_store

        c = self.container
        c.singleton(EventBusProtocol, instance=event_bus)
        c.singleton(DomainEventPublisherProtocol, instance=event_bus)
        c.singleton(CommandBusProtocol, instance=command_bus)
        c.singleton(QueryBusProtocol, instance=query_bus)
        c.singleton(AuditLoggerProtocol, instance=audit_logger)
        c.singleton(InMemoryEventBus, instance=event_bus)
        c.singleton(InMemoryCommandBus, instance=command_bus)
        c.singleton(InMemoryQueryBus, instance=query_bus)
        c.singleton(InMemoryAuditLogger, instance=audit_logger)
        c.singleton(InMemoryDistributedLock, instance=lock)

        if self._extra_registrations is not None:
            self._extra_registrations(c)

        return self

    def make_repository(self) -> InMemoryRepository:
        """Create a fresh :class:`~quadkit.memory.repository.InMemoryRepository`."""
        return InMemoryRepository()

    def make_uow(self) -> InMemoryUnitOfWork:
        """Create a fresh :class:`~quadkit.memory.uow.InMemoryUnitOfWork`."""
        return InMemoryUnitOfWork()

    def teardown(self) -> None:
        """Reset all fakes to their initial state.

        Note: audit logger entries are cleared synchronously via the internal
        list.  Call :meth:`audit_logger.clear` (async) for thread-safe clearing.
        """
        self.event_bus._handlers.clear()
        self.event_bus._wildcard_handlers.clear()
        self.command_bus._handlers.clear()
        self.query_bus._handlers.clear()
        self.audit_logger._entries.clear()


__all__ = ["TestEnvironment"]
