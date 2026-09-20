"""Regression tests for controller ``@websocket`` method registration.

Controller WebSocket methods are mounted as Starlette ``WebSocketRoute``\\s.
Before the fix, they were wrapped by the HTTP endpoint factory
(``Router._create_endpoint``), whose ``Request`` pipeline returns before the
WebSocket handshake completes — every connection died with
``ASGI callable returned without completing handshake`` (HTTP 500).

These tests pin the dedicated factory
(``Router._create_websocket_endpoint``): DI-resolved controller instance,
Quadkit ``WebSocket`` transport wrapper, and a full accept/message loop.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient

from quadkit.web.di.provider import WebProvider
from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.decorators import websocket
from quadkit.web.routing.router import Router
from quadkit.web.transport.websockets import WebSocket as QuadkitWebSocket
from quadkit.web.websocket.handler import AbstractWebSocketHandler


class _OperatorLikeHandler(Controller, AbstractWebSocketHandler):
    """Mirrors the realtime-monitor operator channel wiring."""

    prefix = ""

    def __init__(self) -> None:
        AbstractWebSocketHandler.__init__(self)

    @websocket("/ws/operator")
    async def operator_channel(self, websocket: QuadkitWebSocket) -> None:
        await self.handle(websocket)

    async def on_connect(self, websocket: QuadkitWebSocket) -> None:
        await websocket.accept()
        await websocket.send_json({"ok": True})

    async def on_message(
        self,
        websocket: QuadkitWebSocket,
        message: dict[str, object],
    ) -> None:
        await websocket.send_json({"echo": message})

    async def on_disconnect(self, websocket: QuadkitWebSocket) -> None:
        """No per-connection state to clean up."""


def _mount(handler_cls: type) -> tuple[Starlette, object]:
    """Register ``handler_cls`` routes on a bare Starlette app."""
    container = SimpleNamespace(resolve=AsyncMock(return_value=handler_cls()))
    provider = WebProvider()
    provider.router = Router()  # normally created during provider boot
    starlette = Starlette()
    provider.starlette = starlette

    asyncio.run(
        provider.router_manager.register_controller_routes(handler_cls, container),
    )
    return starlette, container


def test_controller_websocket_method_is_mounted_as_websocket_route() -> None:
    """The decorated method becomes a WebSocketRoute at its declared path."""
    starlette, container = _mount(_OperatorLikeHandler)

    routes = [
        route for route in starlette.router.routes if isinstance(route, WebSocketRoute)
    ]
    assert [route.path for route in routes] == ["/ws/operator"]
    container.resolve.assert_not_awaited()  # resolution is per-connection


def test_controller_websocket_route_completes_handshake() -> None:
    """End-to-end: accept, message loop, and disconnect all work."""
    starlette, container = _mount(_OperatorLikeHandler)

    with TestClient(starlette) as client:
        with client.websocket_connect("/ws/operator") as ws:
            assert ws.receive_json() == {"ok": True}
            ws.send_json({"message": "probe"})
            assert ws.receive_json() == {"echo": {"message": "probe"}}

    container.resolve.assert_awaited_once_with(_OperatorLikeHandler)


def test_controller_websocket_endpoint_receives_quadkit_transport() -> None:
    """The handler method gets the Quadkit WebSocket, not the raw Starlette one."""
    received: list[object] = []

    class _ProbeController(Controller):
        prefix = ""

        @websocket("/ws/probe")
        async def probe(self, websocket: QuadkitWebSocket) -> None:
            received.append(websocket)
            await websocket.accept()

    container = SimpleNamespace(resolve=AsyncMock(return_value=_ProbeController()))
    provider = WebProvider()
    provider.router = Router()  # normally created during provider boot
    starlette = Starlette()
    provider.starlette = starlette
    asyncio.run(
        provider.router_manager.register_controller_routes(_ProbeController, container),
    )

    with TestClient(starlette) as client:
        with client.websocket_connect("/ws/probe"):
            pass

    assert len(received) == 1
    assert isinstance(received[0], QuadkitWebSocket)
