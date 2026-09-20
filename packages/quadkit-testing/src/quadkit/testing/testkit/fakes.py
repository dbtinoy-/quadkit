"""Test-friendly aliases for in-memory fakes from quadkit.testing.memory.

Re-exports all ``InMemory*`` implementations under shorter ``Fake*`` names
that read naturally in test code.

Example::

    from quadkit.testing.testkit.fakes import FakeEventBus, FakeRepository

    event_bus = FakeEventBus()
    repo: FakeRepository[User] = FakeRepository()
"""

from __future__ import annotations

from quadkit.testing.memory.audit import InMemoryAuditLogger as FakeAuditLogger
from quadkit.testing.memory.cqrs import InMemoryCommandBus as FakeCommandBus
from quadkit.testing.memory.cqrs import InMemoryQueryBus as FakeQueryBus
from quadkit.testing.memory.event_bus import InMemoryEventBus as FakeEventBus
from quadkit.testing.memory.lock import InMemoryDistributedLock as FakeLock
from quadkit.testing.memory.outbox import InMemoryOutbox as FakeOutbox
from quadkit.testing.memory.repository import InMemoryRepository as FakeRepository
from quadkit.testing.memory.uow import InMemoryUnitOfWork as FakeUoW

__all__ = [
    "FakeAuditLogger",
    "FakeCommandBus",
    "FakeEventBus",
    "FakeLock",
    "FakeOutbox",
    "FakeQueryBus",
    "FakeRepository",
    "FakeUoW",
]
