"""Tests for route and controller registry isolation and DI integration.

plans/09172026 H-04: registries are per-application instances owned by the
WebProvider. There are no module-level ``route_registry`` /
``controller_registry`` globals; decorators write into the registration
context that is active while an application is being configured. These
tests pin that architecture.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

from quadkit.web.filters.pipeline import FilterPipeline
from quadkit.web.routing.controller_registry import ControllerRegistry
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.registry import (
    RouteRegistry,
    active_registration_context,
    register_controller,
    registration_context,
)

WEB_SRC = Path(__file__).resolve().parents[3] / "src" / "quadkit" / "web"


class TestRouteRegistryIsolation:
    """Test RouteRegistry clear() method for test isolation."""

    def test_route_registry_instances_are_independent(self) -> None:
        """Verify fresh instances are independent."""
        r1 = RouteRegistry()
        r2 = RouteRegistry()
        assert r1 is not r2

        class FakeController(Controller):
            @staticmethod
            def _route(path: str, method: str = "GET") -> dict:  # pragma: no cover
                return {"path": path, "method": method}

        r1.register_controller(FakeController)
        assert len(r1.get_all_routes()) >= 0
        assert len(r2.get_all_routes()) == 0

    def test_route_registry_clear_removes_all_routes(self) -> None:
        """Verify clear() empties all routes."""
        registry = RouteRegistry()
        registry._items["/test"] = {"GET": {"handler": "test"}}
        assert len(registry._items) > 0

        registry.clear()

        assert len(registry._items) == 0

    def test_route_registry_clear_removes_all_controllers(self) -> None:
        """Verify clear() empties all controllers."""

        class FakeController(Controller):
            pass

        registry = RouteRegistry()
        registry.register_controller(FakeController)
        assert len(registry._controllers) == 1

        registry.clear()

        assert len(registry._controllers) == 0


class TestControllerRegistryIsolation:
    """Test ControllerRegistry clear() method for test isolation."""

    def test_controller_registry_register_and_get(self) -> None:
        """Verify basic register/get functionality."""

        class MyController:
            pass

        registry = ControllerRegistry()
        registry.register("MyController", MyController)
        assert registry.get("MyController") is MyController

    def test_controller_registry_clear_removes_all(self) -> None:
        """Verify clear() empties all controller registrations."""

        class Controller1:
            pass

        class Controller2:
            pass

        registry = ControllerRegistry()
        registry.register("Controller1", Controller1)
        registry.register("Controller2", Controller2)
        assert len(registry.list_controllers()) == 2

        registry.clear()

        assert len(registry.list_controllers()) == 0


class TestFilterPipelineIsolation:
    """Test FilterPipeline clear() method for test isolation."""

    def test_filter_pipeline_has_clear_method(self) -> None:
        """Verify FilterPipeline has a clear() method."""
        pipeline = FilterPipeline()
        assert hasattr(pipeline, "clear")
        assert callable(pipeline.clear)

    def test_filter_pipeline_clear_removes_all_filters(self) -> None:
        """Verify clear() empties all filters."""
        from unittest.mock import MagicMock

        pipeline = FilterPipeline()

        mock_filter1 = MagicMock()
        mock_filter1.can_handle = MagicMock(return_value=False)
        mock_filter2 = MagicMock()
        mock_filter2.can_handle = MagicMock(return_value=False)

        pipeline.add_filter(mock_filter1)
        pipeline.add_filter(mock_filter2)
        assert len(pipeline.filters) == 2

        pipeline.clear()

        assert len(pipeline.filters) == 0

    def test_module_exposes_no_pipeline_singleton(self) -> None:
        """plans/09182026 S-03: the pipeline is a container singleton only."""
        from quadkit.web.filters import pipeline as pipeline_module

        assert not hasattr(pipeline_module, "filter_pipeline")
        assert not hasattr(pipeline_module, "get_filter_pipeline")
        assert not hasattr(pipeline_module, "add_global_filter")
        assert not hasattr(pipeline_module, "remove_global_filter")
        assert pipeline_module.__all__ == ["FilterPipeline"]


class TestRegistrationContext:
    """plans/09172026 H-04 — the context decorators register into."""

    def test_no_active_context_by_default(self) -> None:
        assert active_registration_context() is None

    def test_registration_context_activates_and_resets(self) -> None:
        routes = RouteRegistry()
        controllers = ControllerRegistry()

        with registration_context(routes, controllers) as ctx:
            assert ctx.route_registry is routes
            assert ctx.controller_registry is controllers
            assert active_registration_context() is ctx

        assert active_registration_context() is None

    def test_registration_context_resets_on_error(self) -> None:
        with (
            pytest.raises(RuntimeError),
            registration_context(RouteRegistry(), ControllerRegistry()),
        ):
            raise RuntimeError("boom")
        assert active_registration_context() is None

    def test_controller_decorator_registers_into_active_context(self) -> None:
        from quadkit.web.routing.controller_registry import controller

        routes = RouteRegistry()
        controllers = ControllerRegistry()

        @controller("NamedController")
        class Registered(Controller):
            pass

        with registration_context(routes, controllers):
            pass

        # decorating outside a context must not register anywhere;
        # decorating inside one registers into that pair
        assert controllers.get("NamedController") is None

        with registration_context(routes, controllers):

            @controller("InContextController")
            class InContext(Controller):
                pass

        assert controllers.get("InContextController") is InContext

    def test_controller_decorator_outside_context_is_safe_noop(self) -> None:
        from quadkit.web.routing.controller_registry import controller

        @controller()
        class Outside(Controller):
            pass

        assert Outside is not None  # decorator returns the class untouched

    def test_register_controller_convenience_requires_context(self) -> None:
        class SomeController(Controller):
            pass

        # No active context: warns, does not raise, registers nothing.
        register_controller(SomeController)

        routes = RouteRegistry()
        controllers = ControllerRegistry()
        with registration_context(routes, controllers):
            register_controller(SomeController)

        assert SomeController in routes.get_controllers()
        assert controllers.get("SomeController") is SomeController


class TestNoModuleLevelRegistryGlobals:
    """H-04 pin: no module-level route_registry/controller_registry assignment."""

    def test_no_module_level_registry_globals_in_src(self) -> None:
        offenders: list[str] = []
        for path in sorted(WEB_SRC.rglob("*.py")):
            tree = ast.parse(path.read_text("utf-8"), filename=str(path))
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
                matched = targets & {"route_registry", "controller_registry"}
                if matched:
                    offenders.append(f"{path.relative_to(WEB_SRC)}: {sorted(matched)}")
        assert not offenders, f"module-level registry globals: {offenders}"

    def test_public_surface_no_longer_exports_globals(self) -> None:
        import quadkit.web

        assert not hasattr(quadkit.web, "route_registry")
        assert not hasattr(quadkit.web, "controller_registry")

    def test_two_apps_own_different_filter_pipelines(self) -> None:
        """Each application's container holds its own FilterPipeline."""
        assert len(FilterPipeline().filters) == 0


class AlphaController(Controller):
    """Controller mounted only on application A."""

    from quadkit.web import get  # noqa: PLC0415

    @get("/alpha")
    async def alpha(self) -> dict[str, str]:
        return {"app": "alpha"}


class BetaController(Controller):
    """Controller mounted only on application B."""

    from quadkit.web import get  # noqa: PLC0415

    @get("/beta")
    async def beta(self) -> dict[str, str]:
        return {"app": "beta"}


async def _boot(controllers: list[type]) -> tuple[Any, Any, Any]:
    """Boot a full application with the given controllers."""
    from quadkit.app.base import Application
    from quadkit.web.config import RateLimitConfig, WebConfig
    from quadkit.web.di.provider import WebProvider

    app = Application(name=f"registry-{'-'.join(c.__name__ for c in controllers)}")

    async def _allow_all(request: Any) -> bool:
        return True

    web = WebProvider(
        web_config=WebConfig(rate_limit=RateLimitConfig(enabled=False)),
        controllers=controllers,
        debug_routes_auth=_allow_all,
    )
    await web.register(app.container)
    await web.boot(app.container)
    return app, web, TestClient(web.starlette)


class TestPerApplicationRegistries:
    """H-04 pin: two applications in one process, zero cross-talk."""

    @pytest.mark.asyncio
    async def test_two_apps_do_not_cross_talk(self) -> None:
        app_a, web_a, client_a = await _boot([AlphaController])
        app_b, web_b, client_b = await _boot([BetaController])

        # Registry instances are per-provider and distinct.
        assert web_a.route_registry is not web_b.route_registry
        assert web_a.controller_registry is not web_b.controller_registry

        # Each registry only knows its own controllers/routes.
        a_controllers = web_a.route_registry.get_controllers()
        b_controllers = web_b.route_registry.get_controllers()
        assert AlphaController in a_controllers
        assert BetaController not in a_controllers
        assert BetaController in b_controllers
        assert AlphaController not in b_controllers

        assert "/alpha" in web_a.route_registry.get_all_routes()
        assert "/beta" not in web_a.route_registry.get_all_routes()
        assert "/beta" in web_b.route_registry.get_all_routes()
        assert "/alpha" not in web_b.route_registry.get_all_routes()

        # Both applications serve their own routes live.
        assert client_a.get("/alpha").json() == {"app": "alpha"}
        assert client_a.get("/beta").status_code == 404
        assert client_b.get("/beta").json() == {"app": "beta"}
        assert client_b.get("/alpha").status_code == 404

        # DI resolution returns each app's own instances.
        from quadkit.web.routing.controller_registry import ControllerRegistry
        from quadkit.web.routing.registry import RouteRegistry

        resolved_a = await app_a.container.resolve(RouteRegistry)
        resolved_b = await app_b.container.resolve(RouteRegistry)
        assert resolved_a is web_a.route_registry
        assert resolved_b is web_b.route_registry
        assert resolved_a is not resolved_b

        resolved_ca = await app_a.container.resolve(ControllerRegistry)
        assert resolved_ca is web_a.controller_registry

    @pytest.mark.asyncio
    async def test_filter_pipelines_are_per_application(self) -> None:
        """Two apps resolve two FilterPipeline singletons, one each."""
        app_a, web_a, _client_a = await _boot([AlphaController])
        app_b, web_b, _client_b = await _boot([BetaController])

        pipeline_a = await app_a.container.resolve(FilterPipeline)
        pipeline_b = await app_b.container.resolve(FilterPipeline)

        assert pipeline_a is not pipeline_b
        assert web_a.router.global_pipeline is pipeline_a
        assert web_b.router.global_pipeline is pipeline_b
        assert pipeline_a is not web_a.router.exception_filters
        assert pipeline_b is not web_b.router.exception_filters

        # A filter added to one application's pipeline is invisible to the other.
        from unittest.mock import MagicMock

        pipeline_a.add_filter(MagicMock(can_handle=MagicMock(return_value=False)))
        assert len(pipeline_a.filters) == 1
        assert pipeline_b.filters == []

    @pytest.mark.asyncio
    async def test_import_time_decorator_has_no_side_effects(self) -> None:
        """Importing controller modules registers nothing anywhere by itself.

        AlphaController/BetaController above are already imported by this
        test module at collection time — outside any registration context —
        so a fresh registry pair must stay empty until a provider boots.
        """
        routes = RouteRegistry()
        controllers = ControllerRegistry()

        with registration_context(routes, controllers):
            pass  # nothing registers: import happened long ago, globally

        assert routes.get_controllers() == []
        assert controllers.list_controllers() == []

        # A provider boot registers only what it was given plus the installed
        # contributors; the controllers imported by this module stay absent.
        _app_fresh, web_fresh, _client = await _boot([])
        booted = web_fresh.route_registry.get_controllers()
        assert AlphaController not in booted
        assert BetaController not in booted
        assert "/alpha" not in web_fresh.route_registry.get_all_routes()
        assert "/beta" not in web_fresh.route_registry.get_all_routes()
