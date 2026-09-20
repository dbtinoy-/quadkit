from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.applications import Starlette

from quadkit.app.base import Application
from quadkit.web.routing.route_handlers import CoreRouteHandler


class _BypassOnlyContainer:
    def __init__(self, quadkit_app: object) -> None:
        self.quadkit_app = quadkit_app
        self.calls: list[tuple[object, bool]] = []

    async def resolve(
        self, token: object, *, bypass_visibility: bool = False
    ) -> object:
        self.calls.append((token, bypass_visibility))
        if not bypass_visibility:
            raise RuntimeError("application lookup must bypass visibility")
        return self.quadkit_app


@pytest.mark.asyncio
async def test_core_route_handler_bypasses_visibility_for_application_lookup() -> None:
    """CoreRouteHandler should bypass visibility when loading the Quadkit app."""

    async def pending_handler() -> dict[str, bool]:
        return {"ok": True}

    route_def = SimpleNamespace(method="GET", path="/core", handler=pending_handler)
    quadkit_app = SimpleNamespace(_pending_routes=[route_def])
    container = _BypassOnlyContainer(quadkit_app)
    starlette_app = Starlette()
    starlette_app.state.container = container

    manager = SimpleNamespace(
        provider=SimpleNamespace(starlette=starlette_app),
        add_route=AsyncMock(),
    )

    await CoreRouteHandler().register(manager, starlette_app)

    manager.add_route.assert_awaited_once()
    assert quadkit_app._pending_routes == []
    assert (Application, True) in container.calls
