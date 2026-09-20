"""Tests for class-based WebSocket route wrapping."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.exceptions.container import UnresolvableDependencyError
from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.route_handlers import (
    WebSocketRouteHandler,
    _wrap_websocket_handler,
)


@pytest.mark.asyncio
async def test_wrapper_falls_back_when_handler_is_unregistered() -> None:
    """An unregistered handler class is still usable without hiding other errors."""

    class ChatHandler:
        def __init__(self) -> None:
            self.handle = AsyncMock()

    container = SimpleNamespace(
        resolve=AsyncMock(side_effect=UnresolvableDependencyError("missing")),
    )
    starlette_websocket = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(container=container)),
    )

    await _wrap_websocket_handler(ChatHandler)(starlette_websocket)

    container.resolve.assert_awaited_once_with(ChatHandler)


@pytest.mark.asyncio
async def test_discovered_handler_is_mounted_as_websocket_route() -> None:
    """Configured WebSocket handlers are included in normal route setup."""

    class ChatHandler:
        _is_websocket_handler = True
        _ws_path = "/ws/chat/{room_id}"

    provider = WebProvider(websocket_handlers=[ChatHandler])
    from starlette.applications import Starlette
    from starlette.routing import WebSocketRoute

    provider.starlette = Starlette()
    await WebSocketRouteHandler().register(provider.router_manager, provider.starlette)

    routes = [
        route
        for route in provider.starlette.router.routes
        if isinstance(route, WebSocketRoute)
    ]
    assert [route.path for route in routes] == ["/ws/chat/{room_id}"]
