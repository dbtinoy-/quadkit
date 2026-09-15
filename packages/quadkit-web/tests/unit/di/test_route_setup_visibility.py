from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.applications import Starlette

from quadkit.app.base import Application
from quadkit.web.config import WebConfig, WebProviderConfig
from quadkit.web.di.route_setup import RouteSetup


class _BypassOnlyResolver:
    def __init__(
        self,
        *,
        metrics_app: Starlette,
        qk_app: SimpleNamespace,
    ) -> None:
        self.metrics_app = metrics_app
        self.qk_app = qk_app
        self.calls: list[tuple[object, bool]] = []

    async def resolve(
        self, token: object, *, bypass_visibility: bool = False
    ) -> object | None:
        self.calls.append((token, bypass_visibility))

        if token == "prometheus_metrics_app":
            if not bypass_visibility:
                raise RuntimeError("metrics lookup must bypass visibility")
            return self.metrics_app

        if token is Application:
            if not bypass_visibility:
                raise RuntimeError("application lookup must bypass visibility")
            return self.qk_app

        return None


@pytest.mark.asyncio
async def test_configure_bypasses_visibility_for_internal_mounts() -> None:
    """RouteSetup should bypass visibility for internal metrics/app lookups."""
    router_manager = MagicMock()
    router_manager.register_routes = AsyncMock()

    setup = RouteSetup(WebConfig(), WebProviderConfig(), router_manager)
    app = Starlette()
    metrics_app = Starlette()
    qk_app = SimpleNamespace(_asgi_handler=None)
    resolver = _BypassOnlyResolver(
        metrics_app=metrics_app,
        qk_app=qk_app,
    )
    app.state.container = resolver

    await setup.configure(app, resolver, provider_context=object())

    assert any(getattr(route, "path", None) == "/metrics" for route in app.routes)
    assert qk_app._asgi_handler is app
    assert ("prometheus_metrics_app", True) in resolver.calls
    assert (Application, True) in resolver.calls
