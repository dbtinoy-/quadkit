"""Tests for TestEnvironment, ContainerFactory memory implementations, and web fixtures."""

from __future__ import annotations

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
from quadkit.testing.fixtures.bed import TestEnvironment
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
