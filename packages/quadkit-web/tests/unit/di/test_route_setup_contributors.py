from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.applications import Starlette

from quadkit.web.config import WebConfig, WebProviderConfig
from quadkit.web.contributors.registry import WebContributorRegistry
from quadkit.web.di.route_setup import RouteSetup


class _MountingContributor:
    @property
    def contributor_id(self) -> str:
        return "admin"

    def get_controllers(self) -> list[type]:
        return []

    def get_middleware(self) -> list[type]:
        return []

    async def mount_to_app(self, app: Starlette, container: object) -> None:
        app.state.admin_mount_called = True


class _FailingContributor:
    @property
    def contributor_id(self) -> str:
        return "broken"

    def get_controllers(self) -> list[type]:
        return []

    def get_middleware(self) -> list[type]:
        return []

    async def mount_to_app(self, app: Starlette, container: object) -> None:  # noqa: ARG002
        raise RuntimeError("boom")


class _MinimalResolver:
    async def resolve(self, token: object, *, bypass_visibility: bool = False) -> object | None:  # noqa: ARG002
        return None


@pytest.mark.asyncio
async def test_configure_runs_contributor_mounts_and_continues_after_failures() -> None:
    router_manager = MagicMock()
    router_manager.register_routes = AsyncMock()

    registry = WebContributorRegistry()
    registry.register(_FailingContributor())
    registry.register(_MountingContributor())

    provider_context = MagicMock()
    provider_context.contributor_registry = registry

    app = Starlette()
    app.state.container = _MinimalResolver()
    setup = RouteSetup(WebConfig(), WebProviderConfig(), router_manager)

    await setup.configure(app, app.state.container, provider_context=provider_context)

    assert app.state.admin_mount_called is True


@pytest.mark.asyncio
async def test_register_debug_routes_respects_config_gate_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router_manager = MagicMock()
    router_manager.register_routes = AsyncMock()

    app = Starlette()
    setup = RouteSetup(
        WebConfig(debug_routes=True, enable_debug_routes_env_gate=False),
        WebProviderConfig(),
        router_manager,
    )
    configure_mock = AsyncMock()
    monkeypatch.setattr(
        "quadkit.web.integrations.debug.DebugIntegration.configure",
        configure_mock,
    )

    await setup._register_debug_routes(app, _MinimalResolver(), provider_context=None)

    configure_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_debug_routes_respects_config_gate_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router_manager = MagicMock()
    router_manager.register_routes = AsyncMock()

    app = Starlette()
    setup = RouteSetup(
        WebConfig(debug_routes=True, enable_debug_routes_env_gate=True),
        WebProviderConfig(),
        router_manager,
    )
    configure_mock = AsyncMock()
    monkeypatch.setattr(
        "quadkit.web.integrations.debug.DebugIntegration.configure",
        configure_mock,
    )

    await setup._register_debug_routes(app, _MinimalResolver(), provider_context=None)

    configure_mock.assert_awaited_once()
