"""Convention followed: **WebSocket handler pattern** — one class per socket
lifecycle (connect, message, disconnect); handlers are plain classes in
the container, so they participate in DI like anything else.

Echo handler for the WebSocket Echo demo.
"""

from __future__ import annotations

from typing import Any, ClassVar

from quadkit.web.websocket import WebSocket
from quadkit.web.websocket.decorators import websocket_handler
from quadkit.web.websocket.handler import AbstractWebSocketHandler
from websocket_echo.services.rooms import ConnectionRegistry, RoomFullError


@websocket_handler("/ws/echo/{room}")
class EchoHandler(AbstractWebSocketHandler):
    """Echo JSON messages inside a room, tagging them with join order."""

    registry: ClassVar[ConnectionRegistry]  # injected by the provider at register

    async def on_connect(self, websocket: WebSocket) -> None:
        room = websocket.path_params["room"]
        self._room = room
        await websocket.accept()
        try:
            self._member = self.registry.join(room)
        except RoomFullError:
            # Polite refusal: the socket is accepted (so the client can
            # read exactly one message), told why, and then closed.
            await self.send_json(
                websocket, {"type": "error", "reason": "room-full", "room": room}
            )
            await websocket.close(code=1013)
            return
        await self.send_json(
            websocket,
            {
                "type": "hello",
                "room": room,
                "member": self._member,
            },
        )

    async def on_message(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        tagged = {
            "type": "echo",
            "room": self._room,
            "member": self._member,
            "data": message,
        }
        if message.get("broadcast") is True:
            await self.broadcast(tagged)
        else:
            await self.send_json(websocket, tagged)

    async def on_disconnect(self, websocket: WebSocket) -> None:
        if getattr(self, "_room", None):
            self.registry.leave(self._room)


__all__ = ["EchoHandler"]
