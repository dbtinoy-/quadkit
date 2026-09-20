"""Feature tour: WebSockets with real lifecycles.

`@websocket_handler("/ws/ticks/{channel}")` declares the route once; the
class implements `on_connect` / `on_message` / `on_disconnect` and the
framework runs the accept/loop/teardown per connection. Path parameters
bind into `websocket.path_params`; every connection gets its own handler
instance — per-connection state is just attributes.
"""

from typing import Any

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import WebModule
from quadkit.web.websocket.decorators import websocket_handler
from quadkit.web.websocket.handler import AbstractWebSocketHandler
from quadkit.web.transport.websockets import WebSocket


@websocket_handler("/ws/ticks/{channel}")
class TicksHandler(AbstractWebSocketHandler):
    """Echo JSON messages on a channel, tagging them with the channel name."""

    async def on_connect(self, websocket: WebSocket) -> None:
        self._channel = websocket.path_params["channel"]
        await websocket.accept()
        await websocket.send_json({"type": "hello", "channel": self._channel})

    async def on_message(
        self, websocket: WebSocket, message: dict[str, Any]
    ) -> None:
        await websocket.send_json(
            {"type": "tick", "channel": self._channel, "data": message}
        )

    async def on_disconnect(self, websocket: WebSocket) -> None:
        """Per-connection state dies with the instance — nothing to clean."""


def create_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(websocket_handlers=[TicksHandler]))
    return app


@pytest.mark.asyncio
async def test_handshake_echo_and_teardown_roundtrip() -> None:
    async with WebTestBed(create_app()) as bed:
        with bed.client.websocket_connect("/ws/ticks/market") as ws:
            assert ws.receive_json() == {"type": "hello", "channel": "market"}

            ws.send_json({"price": 421.5})
            assert ws.receive_json() == {
                "type": "tick",
                "channel": "market",
                "data": {"price": 421.5},
            }


@pytest.mark.asyncio
async def test_channels_are_independent_connections() -> None:
    async with WebTestBed(create_app()) as bed:
        with (
            bed.client.websocket_connect("/ws/ticks/alpha") as alpha,
            bed.client.websocket_connect("/ws/ticks/beta") as beta,
        ):
            assert alpha.receive_json()["channel"] == "alpha"
            assert beta.receive_json()["channel"] == "beta"

            alpha.send_json({"value": 1})
            beta.send_json({"value": 2})

            assert alpha.receive_json()["data"] == {"value": 1}
            assert beta.receive_json()["data"] == {"value": 2}
