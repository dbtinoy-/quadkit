"""Tests for the Application composition root (app/base.py)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.app.base import Application, AppState
from quadkit.app.exceptions import AppShutdownError
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.di.provider import Provider

_counter = 0


class _QuietProvider(Provider):
    def __init__(self, name: str | None = None) -> None:
        global _counter
        _counter += 1
        super().__init__(name=name or f"quiet-{_counter}")
        self.booted = False
        self.disposed = False
        self.boot_error: Exception | None = None

    async def boot(self, container: Any) -> None:
        if self.boot_error is not None:
            raise self.boot_error
        self.booted = True

    async def shutdown(self) -> None:
        self.disposed = True


def _fresh_app(**kw: Any) -> Application:
    return Application(**kw)


class TestConstruction:
    def test_initial_state(self) -> None:
        app = _fresh_app(name="test-app")
        assert app.state is AppState.CREATED
        assert app.is_running is False
        assert app.name == "test-app"

    def test_config_registered_in_container(self) -> None:
        app = _fresh_app(name="test-app")
        cfg = app.config
        assert cfg is not None
        assert app.container.has(ConfigProtocol) is True

    def test_custom_config_kept(self) -> None:
        from quadkit.config import QuadkitConfig

        cfg = QuadkitConfig()
        app = _fresh_app(config=cfg)
        assert app.config is cfg

    def test_repr(self) -> None:
        app = _fresh_app(name="repr-app")
        assert "repr-app" in repr(app)
        assert "created" in repr(app)

    def test_properties(self) -> None:
        app = _fresh_app()
        assert app.container is app._container  # noqa: SLF001
        assert app.logger is not None
        assert app.providers == []


class TestRegistration:
    def test_add_provider(self) -> None:
        app = _fresh_app()
        p = _QuietProvider()
        app.add_provider(p)
        assert app.providers == [p]

    def test_add_providers_bulk(self) -> None:
        app = _fresh_app()
        a, b = _QuietProvider(), _QuietProvider()
        app.add_providers([a, b])
        assert app.providers == [a, b]

    def test_add_provider_duplicate_name_same_type_deduped(self) -> None:
        # Registry dedupes exact-type duplicates by name (silently).
        app = _fresh_app()
        a, b = _QuietProvider(name="same"), _QuietProvider(name="same")
        app.add_provider(a)
        app.add_provider(b)
        assert app.providers == [a]

    def test_add_provider_duplicate_name_different_type_raises(self) -> None:
        app = _fresh_app()

        class Other(Provider):
            name = "same"

            async def boot(self, container: Any) -> None:
                return None

        app.add_provider(_QuietProvider(name="same"))
        with pytest.raises(ValueError, match="Duplicate provider name"):
            app.add_provider(Other())

    def test_add_provider_after_start_rejected(self) -> None:
        app = _fresh_app()
        app._state = AppState.RUNNING  # noqa: SLF001
        with pytest.raises(RuntimeError, match="Cannot add provider"):
            app.add_provider(_QuietProvider())

    def test_add_module(self) -> None:
        app = _fresh_app()

        class M:
            pass

        app.add_module(M)
        assert app._modules == [M]  # noqa: SLF001

    def test_add_modules_bulk(self) -> None:
        app = _fresh_app()
        a, b = type("A", (), {}), type("B", (), {})
        app.add_modules([a, b])
        assert app._modules == [a, b]  # noqa: SLF001

    def test_add_module_after_start_rejected(self) -> None:
        app = _fresh_app()
        app._state = AppState.STARTING  # noqa: SLF001
        with pytest.raises(RuntimeError, match="Cannot add_module"):
            app.add_module(type("M", (), {}))

    def test_add_middleware(self) -> None:
        app = _fresh_app()

        class Mw:
            async def handle(self, request: Any, call_next: Any) -> Any:
                return await call_next(request)

        app.add_middleware(Mw())
        assert len(app._middleware._middleware) == 1  # noqa: SLF001


class TestBoot:
    async def test_boot_context_manager_full_cycle(self) -> None:
        p = _QuietProvider()
        async with Application.boot(providers=[p]) as app:
            assert app.state is AppState.RUNNING
            assert p.booted is True
        assert app.state is AppState.STOPPED
        assert p.disposed is True

    async def test_boot_with_modules_argument(self) -> None:
        from quadkit.app.module import CoreModule

        async with Application.boot(modules=[CoreModule.configure()]) as app:
            assert app.is_running

    async def test_double_start_rejected(self) -> None:
        app = _fresh_app()
        app._state = AppState.RUNNING  # noqa: SLF001
        with pytest.raises(RuntimeError, match="Cannot start"):
            await app.start()

    async def test_failed_boot_shuts_down_and_stops(self) -> None:
        good = _QuietProvider()
        bad = _QuietProvider()
        bad.boot_error = RuntimeError("provider exploded")
        app = _fresh_app()
        app.add_provider(good)
        app.add_provider(bad)

        with pytest.raises(Exception, match="provider exploded"):
            await app.start()

        assert app.state is AppState.STOPPED
        # Already-booted providers are shut down during cleanup.
        assert good.disposed is True

    async def test_boot_failure_from_lifecycle_still_stops(self) -> None:
        app = _fresh_app()
        app._lifecycle.boot = AsyncMock(side_effect=RuntimeError("lifecycle boom"))  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="lifecycle boom"):
            await app.start()
        assert app.state is AppState.STOPPED


class TestStop:
    async def test_stop_when_created_is_noop(self) -> None:
        app = _fresh_app()
        await app.stop()
        assert app.state is AppState.CREATED

    async def test_stop_when_stopped_is_noop(self) -> None:
        app = _fresh_app()
        app._state = AppState.STOPPED  # noqa: SLF001
        await app.stop()
        assert app.state is AppState.STOPPED

    async def test_stop_from_running(self) -> None:
        p = _QuietProvider()
        app = _fresh_app()
        app.add_provider(p)
        await app.start()
        await app.stop()
        assert app.state is AppState.STOPPED
        assert p.disposed is True

    async def test_stop_when_stopping_is_noop(self) -> None:
        app = _fresh_app()
        app._state = AppState.STOPPING  # noqa: SLF001
        app._lifecycle.shutdown = AsyncMock()  # type: ignore[method-assign]
        await app.stop()
        app._lifecycle.shutdown.assert_not_awaited()  # type: ignore[attr-defined]
        assert app.state is AppState.STOPPING

    async def test_shutdown_error_wrapped(self) -> None:
        p = _QuietProvider()
        app = _fresh_app()
        app.add_provider(p)
        await app.start()
        app._lifecycle.shutdown = AsyncMock(side_effect=OSError("disk gone"))  # type: ignore[method-assign]
        with pytest.raises(AppShutdownError, match="shutdown failed"):
            await app.stop()
        assert app.state is AppState.STOPPED

    async def test_shutdown_timeout_wrapped(self) -> None:
        app = _fresh_app()
        await app.start()
        app._lifecycle.shutdown = AsyncMock(side_effect=TimeoutError())  # type: ignore[method-assign]
        with pytest.raises(AppShutdownError, match="timed out"):
            await app.stop()
        assert app.state is AppState.STOPPED

    async def test_stop_from_starting_after_failed_boot(self) -> None:
        app = _fresh_app()
        bad = _QuietProvider()
        bad.boot_error = RuntimeError("nope")
        app.add_provider(bad)
        with pytest.raises(RuntimeError):
            await app.start()
        # stop() from STOPPED is a safe no-op after failed boot.
        await app.stop()
        assert app.state is AppState.STOPPED


class TestStartupCheck:
    async def test_unavailable_when_not_running(self) -> None:
        from quadkit.contracts.core.health import HealthStatus

        app = _fresh_app(name="probe-app")
        result = await app.startup_check()
        assert len(result.components) == 1
        assert result.components[0].status is HealthStatus.UNHEALTHY
        assert result.components[0].component == "probe-app"

    async def test_running_delegates_to_orchestrator(self) -> None:

        app = _fresh_app(name="probe-app")
        app._state = AppState.RUNNING  # noqa: SLF001
        fake = MagicMock()
        app._orchestrator.run_startup = AsyncMock(return_value=fake)  # type: ignore[method-assign]
        result = await app.startup_check()
        assert result is fake
        app._orchestrator.run_startup.assert_awaited_once()  # type: ignore[attr-defined]


class TestASGICall:
    async def test_http_without_handler_raises(self) -> None:
        app = _fresh_app()
        scope = {"type": "http"}
        with pytest.raises(RuntimeError, match="no ASGI handler"):
            await app(scope, None, None)

    async def test_http_auto_starts_when_created(self) -> None:
        app = _fresh_app()
        calls: list[str] = []

        async def fake_start() -> None:
            calls.append("start")
            app._state = AppState.RUNNING  # noqa: SLF001
            app._asgi_handler = AsyncMock()  # noqa: SLF001

        app.start = fake_start  # type: ignore[method-assign]
        await app({"type": "http"}, None, None)
        assert calls == ["start"]
        app._asgi_handler.assert_awaited_once()  # noqa: SLF001

    async def test_lifespan_delegates(self) -> None:
        app = _fresh_app()
        handled = AsyncMock()
        app._handle_lifespan = handled  # type: ignore[method-assign]
        await app({"type": "lifespan"}, "recv", "send")
        handled.assert_awaited_once_with("recv", "send")


class TestDiscoverModules:
    def test_disabled_and_enabled_filters(self, monkeypatch) -> None:
        from quadkit.app import discovery as disc

        class M1:
            name = "m1"

        class M2:
            name = "m2"

        def fake_eps(group: str = "quadkit.modules") -> dict[str, type]:
            del group
            return {"m1": M1, "m2": M2}

        def fake_dirs_empty(dirs: list) -> dict[str, type]:
            del dirs
            return {}

        monkeypatch.setattr(disc, "discover_modules_from_entry_points", fake_eps)
        monkeypatch.setattr(disc, "discover_modules_from_directories", fake_dirs_empty)

        app = _fresh_app()
        app.discover_modules(disabled=["m1"])
        assert app._modules == [M2]  # noqa: SLF001

        app2 = _fresh_app()
        app2.discover_modules(enabled=["m1"])
        assert app2._modules == [M1]  # noqa: SLF001

        app3 = _fresh_app()
        app3.discover_modules()
        assert app3._modules == [M1, M2]  # noqa: SLF001

    def test_directories_merge_into_discovered(self, monkeypatch, tmp_path) -> None:
        from quadkit.app import discovery as disc

        class M1:
            name = "m1"

        class MDir:
            name = "mdir"

        def fake_eps2(group: str = "quadkit.modules") -> dict[str, type]:
            del group
            return {"m1": M1}

        monkeypatch.setattr(disc, "discover_modules_from_entry_points", fake_eps2)

        class M3:
            name = "m3"

        def fake_dirs(paths):
            return {"m3": M3, "m1": M1}

        monkeypatch.setattr(disc, "discover_modules_from_directories", fake_dirs)
        app = _fresh_app()
        app.discover_modules(directories=[str(tmp_path)])
        # m3 added from directories; m1 already present from entry points.
        assert app._modules == [M1, M3]  # noqa: SLF001
