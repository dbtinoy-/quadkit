"""testkit assertions, environment, fakes and fixtures."""

from __future__ import annotations

from typing import Any

import pytest
from quadkit.contracts.audit import AuditLoggerProtocol
from quadkit.contracts.events import (
    CommandBusProtocol,
    EventBusProtocol,
    QueryBusProtocol,
)
from quadkit.di.container import Container
from quadkit.result import Err, Ok
from quadkit.testing.memory.audit import InMemoryAuditLogger
from quadkit.testing.memory.cqrs import InMemoryCommandBus, InMemoryQueryBus
from quadkit.testing.memory.event_bus import InMemoryEventBus
from quadkit.testing.memory.lock import InMemoryDistributedLock
from quadkit.testing.memory.outbox import InMemoryOutbox
from quadkit.testing.memory.repository import InMemoryRepository
from quadkit.testing.memory.uow import InMemoryUnitOfWork
from quadkit.testing.testkit import (
    FakeAuditLogger,
    FakeCommandBus,
    FakeEventBus,
    FakeLock,
    FakeOutbox,
    FakeQueryBus,
    FakeRepository,
    FakeUoW,
    assert_err_contains,
    assert_err_type,
)
from quadkit.testing.testkit import (
    assert_err as tk_assert_err,
)
from quadkit.testing.testkit import (
    assert_ok as tk_assert_ok,
)
from quadkit.testing.testkit.environment import TestEnvironment as TKTestEnvironment
from quadkit.testing.testkit.fixtures import (
    test_container,
    test_environment,
    test_event_bus,
)

# ---------------------------------------------------------------------------
# testkit assertions
# ---------------------------------------------------------------------------


def test_testkit_assertions() -> None:
    assert tk_assert_ok(Ok(42)) == 42
    assert tk_assert_err(Err("boom")) == "boom"

    class DomainError(Exception):
        pass

    err = assert_err_type(Err(DomainError("d")), DomainError)
    assert isinstance(err, DomainError)
    assert assert_err_contains(Err(ValueError("not found: x")), "not found")

    with pytest.raises(AssertionError, match="Expected Ok but got Err"):
        tk_assert_ok(Err("e"))
    with pytest.raises(AssertionError, match="Expected Err but got Ok"):
        tk_assert_err(Ok(1))
    with pytest.raises(AssertionError, match="Expected error of type"):
        assert_err_type(Err(ValueError("v")), DomainError)
    with pytest.raises(AssertionError, match="Expected error message to contain"):
        assert_err_contains(Err(ValueError("nope")), "missing")


# ---------------------------------------------------------------------------
# testkit environment
# ---------------------------------------------------------------------------


async def test_testkit_environment_setup_resolve_teardown() -> None:
    env = TKTestEnvironment()
    returned = await env.setup()
    assert returned is env
    assert env.event_bus is not None
    assert env.command_bus is not None
    assert env.audit_logger is not None
    assert env.lock is not None

    c = env.container
    assert await c.resolve(EventBusProtocol) is env.event_bus
    assert await c.resolve(CommandBusProtocol) is env.command_bus
    assert await c.resolve(QueryBusProtocol) is env.query_bus
    assert await c.resolve(AuditLoggerProtocol) is env.audit_logger
    assert await c.resolve(InMemoryEventBus) is env.event_bus

    # teardown clears handler registries.
    env.event_bus._handlers["some.event"] = object()
    env.event_bus._wildcard_handlers.append(object())
    env.command_bus._handlers["some.cmd"] = object()
    env.query_bus._handlers["some.q"] = object()
    env.audit_logger._entries.append({"a": 1})
    env.teardown()
    assert env.event_bus._handlers == {}
    assert env.event_bus._wildcard_handlers == []
    assert env.command_bus._handlers == {}
    assert env.query_bus._handlers == {}
    assert len(env.audit_logger._entries) == 0

    repo = env.make_repository()
    uow = env.make_uow()
    assert isinstance(repo, InMemoryRepository)
    assert isinstance(uow, InMemoryUnitOfWork)


async def test_testkit_environment_extra_registrations() -> None:
    seen: dict[str, Any] = {}

    def register(c: Container) -> None:
        seen["container"] = c

    env = TKTestEnvironment(extra_registrations=register)
    await env.setup()
    assert seen["container"] is env.container


# ---------------------------------------------------------------------------
# testkit fakes aliases
# ---------------------------------------------------------------------------


def test_testkit_fake_aliases() -> None:
    assert FakeAuditLogger is InMemoryAuditLogger
    assert FakeCommandBus is InMemoryCommandBus
    assert FakeQueryBus is InMemoryQueryBus
    assert FakeEventBus is InMemoryEventBus
    assert FakeLock is InMemoryDistributedLock
    assert FakeOutbox is InMemoryOutbox
    assert FakeRepository is InMemoryRepository
    assert FakeUoW is InMemoryUnitOfWork


# ---------------------------------------------------------------------------
# testkit fixtures
# ---------------------------------------------------------------------------


async def test_testkit_fixtures() -> None:
    gen = test_environment.__wrapped__()
    env = await gen.__anext__()
    try:
        container = test_container.__wrapped__(env)
        assert container is env.container
        bus = test_event_bus.__wrapped__(env)
        assert bus is env.event_bus
    finally:
        await gen.aclose()
    assert env.event_bus._handlers == {}


# ---------------------------------------------------------------------------
# testkit lazy package facade
# ---------------------------------------------------------------------------


def test_testkit_lazy_imports() -> None:
    import quadkit.testing.testkit as tk

    assert "TestEnvironment" in tk.__dir__()
    assert set(tk.__all__) == set(tk._LAZY_IMPORTS.keys())
    env_cls = tk.TestEnvironment
    assert env_cls is TKTestEnvironment
    assert tk.FakeEventBus is InMemoryEventBus
    assert tk.assert_ok is tk_assert_ok
    with pytest.raises(AttributeError, match="has no attribute"):
        tk.not_a_thing  # noqa: B018
