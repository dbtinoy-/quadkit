"""Tests for quadkit.testing.harness (testbed, decorators, container, environment) and testkit."""

from __future__ import annotations

import sys
from typing import Any

import pytest

from quadkit.app.base import Application
from quadkit.contracts.audit import AuditLoggerProtocol
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.contracts.events import (
    CommandBusProtocol,
    EventBusProtocol,
    QueryBusProtocol,
)
from quadkit.di.container import Container
from quadkit.result import Err, Ok
from quadkit.testing.harness.container import QuadkitContainerHarness
from quadkit.testing.harness.decorators import override
from quadkit.testing.harness.decorators import testbed as tb_decorator
from quadkit.testing.harness.environment import IntegrationEnvironment
from quadkit.testing.harness.overrides import override as override_cm
from quadkit.testing.harness.testbed import AppTestBed, _build_test_client
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
# AppTestBed
# ---------------------------------------------------------------------------


class _Service:
    pass


async def test_app_test_bed_from_factory_callable() -> None:
    captured: dict[str, Any] = {}

    def factory() -> Application:
        app = Application(name="harness-test")
        captured["app"] = app
        return app

    async with AppTestBed.from_factory(factory) as bed:
        assert bed.app is captured["app"]
        assert bed.container is bed.app.container
        assert bed.client is None  # no WebProvider → no HTTP client
        assert bed.app.is_running

    assert not captured["app"].is_running


async def test_app_test_bed_from_factory_string(tmp_path: Any) -> None:
    module_path = tmp_path / "harness_app_mod.py"
    module_path.write_text(
        "from quadkit.app.base import Application\n\n"
        "def create_app() -> Application:\n"
        "    return Application(name='string-factory')\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        async with AppTestBed.from_factory("harness_app_mod:create_app") as bed:
            assert bed.app.name == "string-factory"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("harness_app_mod", None)


async def test_app_test_bed_from_app_and_overrides() -> None:
    app = Application(name="from-app-test")
    impl = _Service()
    async with AppTestBed.from_app(app, overrides={_Service: impl}) as bed:
        resolved = await bed.container.resolve(_Service)
        assert resolved is impl
    assert not app.is_running


async def test_app_test_bed_overrides_take_effect() -> None:
    class Marker:
        pass

    class_impl = Marker()
    async with AppTestBed.from_factory(
        lambda: Application(name="override-test"), overrides={Marker: class_impl}
    ) as bed:
        assert await bed.container.resolve(Marker) is class_impl


def test_app_test_bed_resolve_factory() -> None:
    def _fn() -> None:
        return None

    assert AppTestBed._resolve_factory(_fn) is _fn

    with pytest.raises(TypeError, match="factory must be a callable"):
        AppTestBed._resolve_factory(123)


async def test_app_test_bed_with_web_provider_has_client() -> None:
    from quadkit.web.di.provider import WebProvider

    def factory() -> Application:
        app = Application(name="web-bed-test")
        app.add_provider(WebProvider())
        return app

    async with AppTestBed.from_factory(factory) as bed:
        assert bed.client is not None
        assert bed.app.is_running


def test_build_test_client() -> None:
    import httpx

    async def _asgi(scope: dict, receive: Any, send: Any) -> None:
        return None

    client = _build_test_client(_asgi)
    assert isinstance(client, httpx.AsyncClient)


# ---------------------------------------------------------------------------
# @testbed / @override decorators
# ---------------------------------------------------------------------------


async def test_tb_decorator_boots_and_injects_bed() -> None:
    seen: dict[str, Any] = {}

    @tb_decorator(lambda: Application(name="decorator-test"))
    class TestFlow:
        async def test_boots(self, bed: Any) -> None:
            seen["bed"] = bed
            seen["running"] = bed.app.is_running

        def test_sync_not_wrapped(self) -> None:
            seen["sync"] = True

        async def helper_not_test(self, bed: Any) -> None:  # noqa: ARG002
            seen["helper"] = True

    instance = TestFlow()
    await instance.test_boots()
    instance.test_sync_not_wrapped()
    instance.helper_not_test(None)  # untouched coroutine — call directly

    assert seen["running"] is True
    assert seen["sync"] is True
    assert not seen.get("helper")
    assert TestFlow.__testbed_factory__  # metadata recorded


async def test_tb_decorator_class_and_method_overrides() -> None:
    class PaymentGateway:
        def __init__(self, tag: str) -> None:
            self.tag = tag

    class_impl = PaymentGateway("class")
    method_impl = PaymentGateway("method")

    @tb_decorator(
        lambda: Application(name="override-merge"),
        overrides={PaymentGateway: class_impl},
    )
    class TestOverrides:
        async def test_class_level(self, bed: Any) -> None:
            assert await bed.container.resolve(PaymentGateway) is class_impl

        @override(PaymentGateway, method_impl)
        async def test_method_level(self, bed: Any) -> None:
            assert await bed.container.resolve(PaymentGateway) is method_impl

    instance = TestOverrides()
    await instance.test_class_level()
    await instance.test_method_level()


async def test_tb_decorator_method_without_bed_param() -> None:
    seen: dict[str, Any] = {}

    @tb_decorator(lambda: Application(name="no-bed-param"))
    class TestNoBed:
        async def test_no_bed(self) -> None:
            seen["called"] = True

    await TestNoBed().test_no_bed()
    assert seen["called"] is True


def test_override_decorator_stacks() -> None:
    class A:
        pass

    class B:
        pass

    def _method() -> None:
        return None

    override(A, 1)(override(B, 2)(_method))
    attrs = _method.__dict__["__testbed_method_overrides__"]
    # Outermost decorator (A) is prepended → lowest priority in the merge dict.
    assert attrs == [(A, 1), (B, 2)]


# ---------------------------------------------------------------------------
# QuadkitContainerHarness
# ---------------------------------------------------------------------------


async def test_container_harness_registers_common_protocols() -> None:
    from quadkit.contracts import DatabaseProviderProtocol

    container = QuadkitContainerHarness()
    ok = await container.try_resolve(DatabaseProviderProtocol)
    assert ok.is_ok()
    # The same instance must be stable across resolutions.
    again = await container.try_resolve(DatabaseProviderProtocol)
    assert again.is_ok()
    assert ok.unwrap() is again.unwrap()


def test_container_harness_register_mocks_false() -> None:
    from quadkit.contracts import DatabaseProviderProtocol

    container = QuadkitContainerHarness(register_mocks=False)
    assert container is not None
    assert DatabaseProviderProtocol is not None


async def test_container_harness_try_resolve_err() -> None:
    container = QuadkitContainerHarness(register_mocks=False)
    result = await container.try_resolve(_Service)
    assert result.is_err()


async def test_container_harness_override_and_mock() -> None:
    class Svc:
        def __init__(self, tag: str) -> None:
            self.tag = tag

    container = QuadkitContainerHarness(register_mocks=False)
    original = Svc("original")
    replacement = Svc("replacement")
    container.singleton(Svc, original)

    with container.override(Svc, replacement):
        assert await container.resolve(Svc) is replacement
    assert await container.resolve(Svc) is original

    # Overriding a binding that did not exist → removed on exit.
    other = Svc("other")
    with container.override(Svc, other):
        assert await container.resolve(Svc) is other
    assert await container.resolve(Svc) is original

    mocked = Svc("mocked")
    container.mock(Svc, mocked)
    assert await container.resolve(Svc) is mocked


async def test_container_harness_bind() -> None:
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class Greeter(Protocol):  # type: ignore[valid-type]
        def greet(self) -> str: ...

    class GoodGreeter:
        def greet(self) -> str:
            return "hi"

    class Bad:
        pass

    container = QuadkitContainerHarness(register_mocks=False)
    good = GoodGreeter()
    container.bind(Greeter, good)
    assert isinstance(container, Container)
    assert await container.resolve(Greeter) is good

    with pytest.raises(TypeError, match="does not implement protocol"):
        container.bind(Greeter, Bad())


# ---------------------------------------------------------------------------
# harness.overrides (direct)
# ---------------------------------------------------------------------------


async def test_override_context_manager_direct() -> None:
    class Svc:
        def __init__(self, tag: str) -> None:
            self.tag = tag

    container = Container()
    original = Svc("o")
    swapped = Svc("s")
    container.singleton(Svc, original)

    with override_cm(container, Svc, swapped):
        assert await container.resolve(Svc) is swapped
    assert await container.resolve(Svc) is original


# ---------------------------------------------------------------------------
# IntegrationEnvironment
# ---------------------------------------------------------------------------


async def test_integration_environment_with_database() -> None:
    env = IntegrationEnvironment.with_database()
    assert env._config_overrides == {"database.url": "sqlite+aiosqlite:///:memory:"}
    async with env as entered:
        assert entered is env
        cfg = await env.resolve(ConfigProtocol)
        assert cfg.get("database.url") == "sqlite+aiosqlite:///:memory:"
        assert env.app is not None


async def test_integration_environment_with_cache() -> None:
    env = IntegrationEnvironment.with_cache(
        backend="memory", name="cache-test", config={"cache.extra": "x"}
    )
    assert env._config_overrides == {
        "cache.backend": "memory",
        "cache.extra": "x",
    }
    async with env:
        cfg = await env.resolve(ConfigProtocol)
        assert cfg.get("cache.backend") == "memory"
        assert cfg.get("cache.extra") == "x"

    env_redis = IntegrationEnvironment.with_cache(
        backend="redis", url="redis://localhost:6399/1"
    )
    assert env_redis._config_overrides["cache.url"] == "redis://localhost:6399/1"


async def test_integration_environment_with_all() -> None:
    env = IntegrationEnvironment.with_all(
        cache_backend="memory",
        cache_url="mem://local",
        config={"app.mode": "test"},
    )
    assert env._config_overrides == {
        "database.url": "sqlite+aiosqlite:///:memory:",
        "cache.backend": "memory",
        "cache.url": "mem://local",
        "app.mode": "test",
    }
    async with env:
        cfg = await env.resolve(ConfigProtocol)
        assert cfg.get("app.mode") == "test"


async def test_integration_environment_no_config_overrides() -> None:
    env = IntegrationEnvironment(name="plain")
    assert env._config_overrides == {}
    async with env:
        assert env.app is not None


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
