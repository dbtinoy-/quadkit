"""Tests for TestEnvironment, ContainerFactory memory implementations, and web fixtures."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
from typing import Any

import pytest

from quadkit.app.base import Application
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.contracts.events import (
    CommandBusProtocol,
    EventBusProtocol,
    QueryBusProtocol,
)
from quadkit.testing.fakes import (
    FakeCache,
    FakeConfig,
    FakeEventBus,
    FakeLogger,
    FakeMetricsCollector,
    FakeQueryBus,
    FakeStateStore,
)
from quadkit.testing.fixtures import containers as containers_mod
from quadkit.testing.fixtures.bed import TestEnvironment
from quadkit.testing.fixtures.containers import (
    ContainerFactory,
    apply_overrides,
)
from quadkit.testing.fixtures.web import (
    app_bed,
    authenticated_web_client,
    mock_web_request,
    mock_web_response,
    sample_web_post_data,
    sample_web_user_data,
    web_test_bed,
    web_test_client,
)
from quadkit.testing.mocks.base import MockProvider


class _NamedMock(MockProvider):
    """MockProvider with a distinct name (dict keys are provider.name)."""

    def __init__(self, provider_name: str) -> None:
        super().__init__()
        self.name = provider_name  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# TestEnvironment — construction & registration
# ---------------------------------------------------------------------------


def test_init_with_name() -> None:
    env = TestEnvironment("my-env")
    assert env.name == "my-env"
    assert env.app is None
    assert env._owns_app is True
    assert env.providers == {}
    assert env.mock_providers == {}


def test_init_with_application() -> None:
    app = Application(name="existing")
    env = TestEnvironment(app)
    assert env.name == "existing"
    assert env.app is app
    assert env.container is app.container
    assert env._owns_app is False


def test_registration_helpers_chain() -> None:
    env = TestEnvironment()
    provider = _NamedMock("p1")
    mock_provider = _NamedMock("p2")
    impl = object()

    assert env.use_provider(provider) is env
    assert env.use_mock_provider(mock_provider) is env
    assert env.override(ConfigProtocol, impl) is env
    fixture_fn = lambda: None  # noqa: E731
    assert env.add_fixture("f", fixture_fn) is env

    assert env.get_provider("p1") is provider
    assert env.get_provider("missing") is None
    assert env.get_mock_provider("p2") is mock_provider
    assert env.get_mock_provider("missing") is None
    # use_mock_provider also lands in the general provider dict.
    assert env.providers["p2"] is mock_provider


# ---------------------------------------------------------------------------
# TestEnvironment — fake() / get_fake()
# ---------------------------------------------------------------------------


def test_fake_registry_by_protocol_name() -> None:
    from quadkit.testing.fakes import FakeCommandBus

    env = TestEnvironment()
    env.fake(EventBusProtocol).fake(CommandBusProtocol).fake(QueryBusProtocol)
    assert isinstance(env.get_fake(EventBusProtocol), FakeEventBus)
    assert isinstance(env.get_fake(CommandBusProtocol), FakeCommandBus)
    assert isinstance(env.get_fake(QueryBusProtocol), FakeQueryBus)


def test_fake_registry_aliases() -> None:
    import quadkit.contracts as oc

    # The registry is name-based: contracts that are not importable in this
    # environment are exercised through stand-in classes with the same name.
    logger_proto = type("Logger", (), {})
    metrics_proto = type("MetricsCollectorProtocol", (), {})
    recorder_proto = type("MetricsRecorderProtocol", (), {})
    cache_alias = type("CacheProtocol", (), {})
    config_alias = type("Config", (), {})

    env = TestEnvironment()
    env.fake(logger_proto).fake(oc.CacheBackendProtocol)
    env.fake(oc.StateStoreProtocol).fake(metrics_proto)
    env.fake(ConfigProtocol)

    assert isinstance(env.get_fake(logger_proto), FakeLogger)
    assert isinstance(env.get_fake(oc.CacheBackendProtocol), FakeCache)
    assert isinstance(env.get_fake(oc.StateStoreProtocol), FakeStateStore)
    assert isinstance(env.get_fake(metrics_proto), FakeMetricsCollector)
    assert isinstance(env.get_fake(ConfigProtocol), FakeConfig)

    env2 = TestEnvironment()
    env2.fake(cache_alias).fake(config_alias).fake(recorder_proto)
    assert isinstance(env2.get_fake(cache_alias), FakeCache)
    assert isinstance(env2.get_fake(config_alias), FakeConfig)
    assert isinstance(env2.get_fake(recorder_proto), FakeMetricsCollector)


def test_fake_registry_by_fake_class() -> None:
    env = TestEnvironment()
    env.fake(FakeEventBus).fake(FakeLogger).fake(FakeConfig)
    assert isinstance(env.get_fake(FakeEventBus), FakeEventBus)
    assert isinstance(env.get_fake(FakeLogger), FakeLogger)
    assert isinstance(env.get_fake(FakeConfig), FakeConfig)


def test_fake_unknown_raises() -> None:
    class UnknownContract:
        pass

    env = TestEnvironment()
    with pytest.raises(ValueError, match="No fake registered"):
        env.fake(UnknownContract)
    with pytest.raises(ValueError, match=r"Did you call env\.fake"):
        env.get_fake(UnknownContract)


# ---------------------------------------------------------------------------
# TestEnvironment — lifecycle
# ---------------------------------------------------------------------------


async def test_setup_creates_and_starts_app() -> None:
    env = TestEnvironment("setup-test")
    env.use_provider(_NamedMock("setup-provider"))
    impl = FakeConfig({"a.b": 1})
    env.override(ConfigProtocol, impl)

    app = await env.setup()
    assert env.app is app
    assert env.container is app.container
    assert env.container is not None
    assert await env.resolve(ConfigProtocol) is impl
    assert env.providers["setup-provider"].is_booted
    # Convenience ASGI hook attribute.
    assert hasattr(app, "set_asgi_handler")
    await env.teardown()
    assert env.app is None
    assert env.container is None


async def test_setup_noop_when_already_running() -> None:
    env = TestEnvironment("noop-test")
    first = await env.setup()
    second = await env.setup()
    assert second is first
    await env.teardown()


async def test_setup_restarts_when_new_provider_added() -> None:
    env = TestEnvironment("restart-test")
    env.use_provider(_NamedMock("first"))
    first_app = await env.setup()

    env.use_provider(_NamedMock("second"))
    second_app = await env.setup()
    from quadkit.app.base import AppState

    assert second_app is not first_app
    assert second_app.state == AppState.RUNNING
    # Both providers booted on the new app.
    assert env.providers["first"].is_booted
    assert env.providers["second"].is_booted
    await env.teardown()


async def test_teardown_stops_owned_app_only() -> None:
    env = TestEnvironment()
    env.use_provider(_NamedMock("owned"))
    await env.setup()
    await env.teardown()
    assert env.app is None

    # Borrowed app: teardown shuts providers down but keeps the app.
    app = Application(name="borrowed")
    env2 = TestEnvironment(app)
    env2.use_provider(_NamedMock("borrowed-provider"))
    await app.start()
    await env2.teardown()
    assert env2.app is app  # not nulled — we don't own it
    await app.stop()


async def test_teardown_tolerates_failing_providers() -> None:
    class ExplodingProvider(MockProvider):
        name: str = "exploding"

        async def shutdown(self) -> None:
            msg = "cannot shut down"
            raise RuntimeError(msg)

    env = TestEnvironment()
    env.use_provider(ExplodingProvider())
    await env.setup()
    await env.teardown()  # must not raise
    assert env.app is None


async def test_teardown_providers_noop() -> None:
    env = TestEnvironment()
    result = await env.teardown_providers()
    assert result is None


async def test_context_manager() -> None:
    env = TestEnvironment("ctx-test")
    async with env.context() as entered:
        assert entered is env
        assert env.app is not None
    assert env.app is None


async def test_aenter_aexit() -> None:
    env = TestEnvironment("aenter-test")
    async with env as entered:
        assert entered is env
        assert env.app is not None
    assert env.app is None


async def test_resolve_before_setup_raises() -> None:
    env = TestEnvironment()
    with pytest.raises(RuntimeError, match="not set up yet"):
        await env.resolve(ConfigProtocol)
    with pytest.raises(RuntimeError, match="not set up yet"):
        env.resolve_sync(ConfigProtocol)


def test_create_mock() -> None:
    env = TestEnvironment()
    instance = env.create_mock(MockProvider)
    assert isinstance(instance, MockProvider)


# ---------------------------------------------------------------------------
# TestEnvironment — health_check
# ---------------------------------------------------------------------------


async def test_health_check_no_app() -> None:
    env = TestEnvironment()
    assert await env.health_check() == {}


async def test_health_check_with_app() -> None:
    env = TestEnvironment("health-test")
    env.use_provider(_NamedMock("healthy"))
    await env.setup()
    try:
        health = await env.health_check()
        assert "healthy" in health
        entry = health["healthy"]
        assert entry["status"] == "healthy"
    finally:
        await env.teardown()


# ---------------------------------------------------------------------------
# apply_overrides
# ---------------------------------------------------------------------------


def test_apply_overrides_singleton_path() -> None:
    from quadkit.di.container import Container

    container = Container()
    impl = FakeConfig({"a.b": 1})
    apply_overrides(container, {ConfigProtocol: impl})
    instance = container.resolve_sync(ConfigProtocol)
    assert instance is impl


def test_apply_overrides_transient_path() -> None:
    class TransientOnly:
        def __init__(self) -> None:
            self.registered: list[tuple] = []

        def transient(self, interface: type, factory: Any) -> None:
            self.registered.append((interface, factory))

    container = TransientOnly()
    impl = object()
    apply_overrides(container, {ConfigProtocol: impl})
    assert len(container.registered) == 1
    assert container.registered[0][0] is ConfigProtocol
    assert container.registered[0][1]() is impl


def test_apply_overrides_no_api_raises() -> None:
    class NoApi:
        pass

    with pytest.raises(RuntimeError, match="does not support known registration"):
        apply_overrides(NoApi(), {ConfigProtocol: object()})


# ---------------------------------------------------------------------------
# ContainerFactory.create_test_container + memory implementations
# ---------------------------------------------------------------------------


async def test_create_test_container_registers_protocols() -> None:
    import quadkit.contracts as oc

    container = ContainerFactory().create_test_container()

    state_store = await container.resolve(oc.StateStoreProtocol)
    await state_store.set("k", "v")
    assert await state_store.get("k") == "v"

    secret_store = await container.resolve(oc.SecretStoreProtocol)
    secret_store.set_secret("s", "v")
    assert secret_store.get_secret("s") == "v"

    lock = await container.resolve(oc.AsyncLockProtocol)
    assert await lock.acquire() is True
    lock.release()
    assert lock.locked() is False

    # Provider protocol mocks registered by the harness convention.
    from quadkit.contracts import (
        AuthProviderProtocol,
        CacheProviderProtocol,
        DatabaseProviderProtocol,
        TaskProviderProtocol,
    )

    db = await container.resolve(DatabaseProviderProtocol)
    assert await db.is_connected() is True
    cache = await container.resolve(CacheProviderProtocol)
    assert cache is not None
    auth = await container.resolve(AuthProviderProtocol)
    assert await auth.verify_token("t") is False
    task = await container.resolve(TaskProviderProtocol)
    assert task.get_worker_stats() == {}


def test_memory_lock_store() -> None:
    factory = ContainerFactory()
    lock = factory._create_memory_lock_store()

    assert lock.locked() is False
    import asyncio

    assert asyncio.run(lock.acquire()) is True
    assert lock.locked() is True
    # Non-blocking re-acquire while held → False.
    assert asyncio.run(lock.acquire()) is False
    lock.release()
    assert lock.locked() is False
    with pytest.raises(RuntimeError, match="Lock is not held"):
        lock.release()

    async def _ctx() -> bool:
        async with lock as entered:
            assert entered is lock
            assert lock.locked() is True
        return lock.locked() is False

    assert asyncio.run(_ctx())


async def test_memory_pubsub() -> None:
    pubsub = ContainerFactory()._create_memory_pubsub()
    received: list[Any] = []

    async def handler(message: Any) -> None:
        received.append(message)

    await pubsub.publish("ch", "before")  # no subscribers → no-op
    assert received == []
    await pubsub.subscribe("ch", handler)
    await pubsub.subscribe("ch", handler)
    await pubsub.publish("ch", "hello")
    assert received == ["hello", "hello"]

    # unsubscribe removes one registered instance of the callback.
    await pubsub.unsubscribe("ch", handler)
    await pubsub.publish("ch", "after")
    assert received == ["hello", "hello", "after"]
    await pubsub.unsubscribe("ch", handler)
    await pubsub.publish("ch", "gone")
    assert received == ["hello", "hello", "after"]
    # Unsubscribe from unknown channel → no-op.
    await pubsub.unsubscribe("unknown", handler)


def test_memory_secret_store() -> None:
    store = ContainerFactory()._create_memory_secret_store()
    assert store.has_secret("s") is False
    store.set_secret("s", "v1")
    assert store.get_secret("s") == "v1"
    assert store.has_secret("s") is True
    store.set_secret("s", "v2")
    assert store.get_secret("s") == "v2"
    store.delete_secret("s")
    assert store.has_secret("s") is False
    store.delete_secret("s")  # idempotent

    from quadkit.contracts.exceptions.components import SecretNotFoundError

    with pytest.raises(SecretNotFoundError, match="Secret 'missing' not found"):
        store.get_secret("missing")


async def test_memory_state_store_basic() -> None:
    store = ContainerFactory()._create_memory_state_store()
    assert await store.get("k") is None
    assert await store.exists("k") is False
    assert await store.delete("k") is False

    await store.set("k", "v")
    assert await store.get("k") == "v"
    assert await store.exists("k") is True
    assert await store.ttl("k") == -1  # no expiry

    await store.set("k2", "v2", ttl=100)
    assert await store.ttl("k2") >= 99
    assert await store.expire("k2", 50) is True
    assert 49 <= await store.ttl("k2") <= 50
    assert await store.expire("nope", 5) is False

    assert await store.delete("k") is True
    assert await store.get("k") is None

    # set without ttl clears a previous expiry.
    await store.set("k3", "v3", ttl=100)
    await store.set("k3", "v3b")
    assert await store.ttl("k3") == -1


async def test_memory_state_store_expiry() -> None:
    import asyncio

    store = ContainerFactory()._create_memory_state_store()
    await store.set("k", "v", ttl=1)
    assert await store.get("k") == "v"

    await asyncio.sleep(1.05)
    assert await store.get("k") is None  # expired → deleted
    assert await store.exists("k") is False
    assert await store.ttl("k") == -2

    # get_many / set_many
    await store.set_many({"a": 1, "b": 2}, ttl=60)
    many = await store.get_many(["a", "b", "missing"])
    assert many == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
# fixtures/web.py
# ---------------------------------------------------------------------------


def test_web_sync_fixtures() -> None:
    client = web_test_client.__wrapped__()
    assert client is not None

    request = mock_web_request.__wrapped__()
    assert request.method == "GET"
    assert request.headers["Content-Type"] == "application/json"
    assert request.query_params == {}

    response = mock_web_response.__wrapped__()
    assert response.status_code == 200

    user = sample_web_user_data.__wrapped__()
    assert user["username"] == "testuser"
    post = sample_web_post_data.__wrapped__()
    assert post["title"] == "Test Post"


async def test_web_test_bed_fixture() -> None:
    gen = web_test_bed.__wrapped__()
    bed = await gen.__anext__()
    try:
        assert bed.app is not None
        assert bed.client is not None
    finally:
        await gen.aclose()


async def test_authenticated_web_client_fixture() -> None:
    client = web_test_client.__wrapped__()
    # Return-style async fixture → plain coroutine, not a generator.
    result = await authenticated_web_client.__wrapped__(client)
    assert result is client


async def test_app_bed_no_entry_point() -> None:
    from quadkit.cli.registry import server as server_mod

    original = server_mod.discover_entry_point
    server_mod.discover_entry_point = lambda: None
    try:
        gen = app_bed.__wrapped__()
        value = await gen.__anext__()
        await gen.aclose()
        assert value is None
    finally:
        server_mod.discover_entry_point = original


async def test_app_bed_discovers_create_app(tmp_path: Any, monkeypatch: Any) -> None:
    from quadkit.cli.registry import server as server_mod

    src = tmp_path / "src" / "demo_app"
    src.mkdir(parents=True)
    app_file = src / "app.py"
    app_file.write_text(
        "from quadkit.app.base import Application\n\n"
        "def create_app() -> Application:\n"
        "    return Application(name='discovered-app')\n",
        encoding="utf-8",
    )

    original = server_mod.discover_entry_point
    # app_bed converts relative paths rooted at "src" into dotted modules,
    # so the entry point must be discovered relative to the tmp root.
    server_mod.discover_entry_point = lambda: "src/demo_app/app.py"
    # module path strips "src" → demo_app must be importable from tmp/src
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    monkeypatch.chdir(tmp_path)
    try:
        gen = app_bed.__wrapped__()
        bed = await gen.__anext__()
        assert bed is not None
        assert bed.app.name == "discovered-app"
        await gen.aclose()
    finally:
        server_mod.discover_entry_point = original
        sys.modules.pop("demo_app.app", None)


async def test_app_bed_no_create_app_function(tmp_path: Any) -> None:
    from quadkit.cli.registry import server as server_mod

    src = tmp_path / "src" / "other_app"
    src.mkdir(parents=True)
    app_file = src / "app.py"
    app_file.write_text("VALUE = 1\n", encoding="utf-8")

    original = server_mod.discover_entry_point
    server_mod.discover_entry_point = lambda: str(app_file)
    try:
        gen = app_bed.__wrapped__()
        value = await gen.__anext__()
        await gen.aclose()
        assert value is None
    finally:
        server_mod.discover_entry_point = original


# ---------------------------------------------------------------------------
# ast sanity: app_bed parses real module source
# ---------------------------------------------------------------------------


def test_ast_function_detection_helper() -> None:
    source = "def create_app():\n    return 1\n"
    tree = ast.parse(source)
    found = [
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert found == ["create_app"]
    assert Path("src/x/app.py").with_suffix("") == Path("src/x/app")


# ---------------------------------------------------------------------------
# containers module surface
# ---------------------------------------------------------------------------


def test_containers_all_exports() -> None:
    assert containers_mod.__all__ == [
        "ContainerFactory",
        "apply_overrides",
        "rebind_overrides",
    ]
    factory = ContainerFactory()
    assert "DatabaseProviderProtocol" in factory._common_protocols
    assert "StateStoreProtocol" in factory._common_protocols
