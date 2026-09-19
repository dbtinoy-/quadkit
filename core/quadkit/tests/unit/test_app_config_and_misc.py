"""App config discovery, constants, exceptions, and provider discovery."""

from __future__ import annotations

import pytest

from quadkit.app.base import Application, AppState
from quadkit.app.config import ModuleDiscoveryConfig
from quadkit.app.config.discovery import ModuleDiscoveryConfig as DottedDiscoveryConfig
from quadkit.app.constants import (
    DEFAULT_APP_NAME,
    DEFAULT_HEALTH_CHECK_TIMEOUT,
    DEFAULT_SHUTDOWN_TIMEOUT,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
)
from quadkit.app.exceptions import (
    AppError,
    AppShutdownError,
    AppStartupError,
)
from quadkit.contracts.exceptions import QuadkitError


class TestModuleDiscoveryConfig:
    def test_defaults(self) -> None:
        cfg = ModuleDiscoveryConfig()
        assert cfg.entry_point_group == "quadkit.modules"
        assert cfg.directories == []
        assert cfg.enabled_modules == []
        assert cfg.disabled_modules == []
        assert cfg.auto_discover is False

    def test_is_same_class_as_discovery_module(self) -> None:
        assert ModuleDiscoveryConfig is DottedDiscoveryConfig

    def test_custom(self) -> None:
        cfg = ModuleDiscoveryConfig(
            entry_point_group="custom.modules",
            directories=["/opt/modules"],
            enabled_modules=["a"],
            disabled_modules=["b"],
            auto_discover=True,
        )
        assert cfg.entry_point_group == "custom.modules"
        assert cfg.directories == ["/opt/modules"]
        assert cfg.enabled_modules == ["a"]
        assert cfg.disabled_modules == ["b"]
        assert cfg.auto_discover is True


class TestAppConstants:
    def test_values(self) -> None:
        assert ENV_PREFIX == "QK_APP__"
        assert ENV_NESTED_DELIMITER == "__"
        assert DEFAULT_APP_NAME == "quadkit-app"
        assert DEFAULT_SHUTDOWN_TIMEOUT == 30.0
        assert DEFAULT_HEALTH_CHECK_TIMEOUT == 5.0


class TestAppExceptions:
    def test_hierarchy_and_codes(self) -> None:
        assert issubclass(AppStartupError, AppError)
        assert issubclass(AppShutdownError, AppError)
        assert issubclass(AppError, QuadkitError)
        assert AppError._code == "QK_ERR_APP_001"
        assert AppStartupError._code == "QK_ERR_APP_002"
        assert AppShutdownError._code == "QK_ERR_APP_003"

    def test_raise_and_catch(self) -> None:
        with pytest.raises(AppError):
            raise AppStartupError("boom")
        with pytest.raises(QuadkitError):
            raise AppShutdownError("kaput")


class TestApplicationProviderDiscovery:
    def test_add_providers(self) -> None:
        from quadkit.di.provider import Provider

        app = Application(name="t1")
        p1 = Provider.__subclasses__()[0]()
        p2 = Provider.__subclasses__()[0]()
        p1.name, p2.name = "t1-p1", "t1-p2"
        app.add_providers([p1, p2])
        assert len(app.providers) == 2

    def test_add_module_state_guard(self) -> None:
        app = Application(name="t2")
        app.add_module(type("M1", (), {"name": "m1"}))
        assert len(app._modules) == 1

        class FakeRunning(Application):
            @property
            def state(self) -> AppState:
                return AppState.RUNNING

        running = FakeRunning(name="t3")
        running._state = AppState.RUNNING
        with pytest.raises(RuntimeError, match="Cannot add_module after boot"):
            running.add_module(type("M2", (), {"name": "m2"}))

    def test_add_modules(self) -> None:
        app = Application(name="t4")
        app.add_modules([type("A", (), {}), type("B", (), {})])
        assert len(app._modules) == 2

    def test_discover_providers_from_real_package(self) -> None:
        app = Application(name="t5")
        app.discover_providers("quadkit.security")
        from quadkit.security.provider import SecurityProvider

        assert any(isinstance(p, SecurityProvider) for p in app.providers)

    async def test_asgi_call_without_handler_raises(self) -> None:
        app = Application(name="t6")
        with pytest.raises(RuntimeError, match="no ASGI handler"):
            await app({"type": "http"}, None, None)
