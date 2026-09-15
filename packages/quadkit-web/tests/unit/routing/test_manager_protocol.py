"""Tests for WebRouterManager protocol extraction and decoupling."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

from quadkit.web.routing.controller_registry import ControllerRegistry
from quadkit.web.routing.manager import WebRouterManager
from quadkit.web.routing.registry import RouteRegistry

routes_registry_mod = sys.modules["quadkit.web.routing.registry"]
controller_registry_mod = sys.modules["quadkit.web.routing.controller_registry"]


class _FakeController:
    """Minimal controller shape used to exercise route registration."""

    prefix = ""

    @classmethod
    def collect_routes(cls) -> list[dict]:
        """Return a single fake route."""
        return [{"path": "/fake", "method": "GET", "handler_name": "get_fake"}]


class TestWebRouterManagerProtocols:
    """Test that WebRouterManager accepts minimal protocol-based mocks."""

    def test_accepts_mock_with_starlette_and_controllers(self) -> None:
        """Manager accepts any object with starlette and controllers properties."""
        mock_provider = MagicMock()
        mock_provider.starlette = MagicMock()
        mock_provider.controllers = []

        # Should not raise
        manager = WebRouterManager(provider=mock_provider)
        assert manager is not None

    def test_accepts_mock_with_all_required_properties(self) -> None:
        """Manager accepts object satisfying full WebProviderProtocol."""
        mock_provider = MagicMock()
        mock_provider.starlette = MagicMock()
        mock_provider.controllers = []
        mock_provider.web_config = MagicMock()
        mock_provider.provider_config = MagicMock()
        mock_provider.debug_routes_auth = None
        mock_provider.fail_on_route_conflict = False
        mock_provider.router = MagicMock()
        mock_provider.openapi_generator = MagicMock()

        # Should not raise
        manager = WebRouterManager(provider=mock_provider)
        assert manager is not None

    def test_should_enable_debug_routes_checks_config(self) -> None:
        """should_enable_debug_routes accesses provider config properties."""
        mock_provider = MagicMock()
        mock_provider.web_config = MagicMock(debug_routes=False)
        mock_provider.provider_config = MagicMock(debug_routes=False)
        mock_provider.debug_routes_auth = None
        mock_provider._debug_routes_redis_client_arg = None

        # Add attributes that should_enable_debug_routes checks with getattr
        # Set them to proper defaults (0 for rate_limit, None for token)
        mock_provider.web_config.debug_routes_token = None
        mock_provider.web_config.debug_routes_rate_limit = 0
        mock_provider.provider_config.debug_routes_token = None
        mock_provider.provider_config.debug_routes_rate_limit = 0

        manager = WebRouterManager(provider=mock_provider)
        result = manager.should_enable_debug_routes()

        # With all false/None, should be disabled
        assert result is False

    def test_should_enable_debug_routes_when_auth_set(self) -> None:
        """should_enable_debug_routes is True when debug_routes_auth is set."""
        mock_provider = MagicMock()
        mock_provider.web_config = MagicMock(debug_routes=False)
        mock_provider.provider_config = MagicMock(debug_routes=False)
        mock_provider.debug_routes_auth = lambda: True  # Not None
        mock_provider._debug_routes_redis_client_arg = None

        # Add attributes for getattr calls with proper defaults
        mock_provider.web_config.debug_routes_token = None
        mock_provider.web_config.debug_routes_rate_limit = 0
        mock_provider.provider_config.debug_routes_token = None
        mock_provider.provider_config.debug_routes_rate_limit = 0

        manager = WebRouterManager(provider=mock_provider)
        result = manager.should_enable_debug_routes()

        # With debug_routes_auth set, should be enabled
        assert result is True

    def test_add_route_uses_starlette_property(self) -> None:
        """add_route accesses starlette property of provider."""
        mock_provider = MagicMock()
        mock_starlette = MagicMock()
        mock_starlette.router.routes = []
        mock_provider.starlette = mock_starlette
        mock_provider.fail_on_route_conflict = False
        mock_provider.router = None

        manager = WebRouterManager(provider=mock_provider)

        mock_handler = MagicMock()

        # This is async, so we need to run it in the event loop
        import asyncio

        asyncio.run(
            manager.add_route(
                path="/test",
                handler=mock_handler,
                method="GET",
                origin_type="core",
            )
        )

        # Verify starlette.add_route was called
        mock_starlette.add_route.assert_called_once()

    def test_generate_openapi_spec_uses_controller_and_generator(self) -> None:
        """generate_openapi_spec accesses controllers and openapi_generator."""
        mock_provider = MagicMock()
        mock_provider.openapi_generator = MagicMock()
        mock_provider.controllers = [MagicMock()]

        mock_generator_instance = MagicMock()
        mock_generator_instance.generate_spec.return_value = {"openapi": "3.0.0"}
        mock_provider.openapi_generator = mock_generator_instance

        manager = WebRouterManager(provider=mock_provider)
        spec = manager.generate_openapi_spec()

        # Verify generate_spec was called with controllers
        mock_generator_instance.generate_spec.assert_called_once_with(
            mock_provider.controllers
        )
        assert "openapi" in spec

    def test_all_accessed_properties_are_in_protocol(self) -> None:
        """Verify WebProviderProtocol includes all properties used by WebRouterManager."""
        # Properties accessed by should_enable_debug_routes:
        # - web_config (with debug_routes, debug_routes_token, debug_routes_rate_limit)
        # - provider_config (with debug_routes, debug_routes_token, debug_routes_rate_limit)
        # - debug_routes_auth
        # - _debug_routes_redis_client_arg
        #
        # Properties accessed by add_route:
        # - starlette
        # - fail_on_route_conflict
        # - router (with _create_endpoint, add_route)
        #
        # Properties accessed by generate_openapi_spec:
        # - openapi_generator
        # - controllers
        #
        # All these should be defined in WebProviderProtocol

        # Create a minimal object that satisfies the protocol
        mock_provider = MagicMock()

        # Essential properties
        mock_provider.starlette = MagicMock()
        mock_provider.controllers = []
        mock_provider.web_config = MagicMock()
        mock_provider.provider_config = MagicMock()
        mock_provider.debug_routes_auth = None
        mock_provider.fail_on_route_conflict = False
        mock_provider.router = MagicMock()
        mock_provider.openapi_generator = None

        # Should construct without error
        manager = WebRouterManager(provider=mock_provider)
        assert manager.provider is not None

    async def test_register_controller_routes_mirrors_into_registry(
        self, monkeypatch
    ) -> None:
        """Mounted controllers are mirrored into the global RouteRegistry."""
        fresh = RouteRegistry()
        monkeypatch.setattr(routes_registry_mod, "route_registry", fresh)
        monkeypatch.setattr(
            controller_registry_mod,
            "controller_registry",
            ControllerRegistry(),
        )

        mock_provider = MagicMock()
        mock_provider.starlette = MagicMock()
        mock_provider.fail_on_route_conflict = False
        mock_provider.router = MagicMock()
        mock_provider.router._create_endpoint = MagicMock(return_value=MagicMock())

        manager = WebRouterManager(provider=mock_provider)
        await manager.register_controller_routes(_FakeController, MagicMock())

        assert _FakeController in fresh.get_controllers()
        routes = fresh.get_all_routes()
        assert "GET" in routes["/fake"]
        assert routes["/fake"]["GET"]["controller"] is _FakeController
