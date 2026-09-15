"""
WebSocket guard support for securing WebSocket connections.

Guards run during the handshake phase before connection is accepted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.result import Err, Ok, Result
from quadkit.web.security.guards import GuardRejection

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from quadkit.web.security.guards import GuardProtocol


async def execute_websocket_guards(
    guards: list[GuardProtocol], websocket: WebSocket
) -> Result[None, GuardRejection]:
    """
    Execute guards during WebSocket handshake.

    Args:
        guards: List of guard instances
        websocket: The WebSocket connection

    Returns:
        Ok(None) if all guards pass, Err(GuardRejection) if any guard fails
    """
    for guard in guards:
        can_proceed = await guard.can_activate(websocket)  # type: ignore[arg-type]
        if not can_proceed:
            await websocket.close(code=4003, reason="Forbidden")
            return Err(GuardRejection())

    return Ok(None)


class GuardedWebSocket:
    """
    WebSocket wrapper that enforces guards during connection.

    Usage:
        @websocket("/chat")
        @use_guards(AuthGuard)
        async def chat(self, ws: WebSocket):
            guarded_ws = GuardedWebSocket(ws, guards)
            await guarded_ws.accept()
            ...
    """

    def __init__(self, websocket: WebSocket, guards: list[GuardProtocol] | None = None):
        self.websocket = websocket
        self.guards = guards or []
        self._accepted = False

    async def accept(self, subprotocol: str | None = None) -> Any:
        """
        Accept WebSocket connection after running guards.

        Args:
            subprotocol: Optional WebSocket subprotocol

        Raises:
            WebSocketDisconnect: If guards fail
        """
        if self.guards:
            result = await execute_websocket_guards(self.guards, self.websocket)
            if result.is_err():
                return  # Connection already closed by guard

        await self.websocket.accept(subprotocol=subprotocol)
        self._accepted = True

    async def send_text(self, data: str) -> Any:
        """Send text message."""
        await self.websocket.send_text(data)

    async def send_bytes(self, data: bytes) -> Any:
        """Send binary message."""
        await self.websocket.send_bytes(data)

    async def send_json(self, data: Any) -> Any:
        """Send JSON message."""
        await self.websocket.send_json(data)

    async def receive_text(self) -> str:
        """Receive text message."""
        return await self.websocket.receive_text()

    async def receive_bytes(self) -> bytes:
        """Receive binary message."""
        return await self.websocket.receive_bytes()

    async def receive_json(self) -> Any:
        """Receive JSON message."""
        return await self.websocket.receive_json()

    async def close(self, code: int = 1000, reason: str | None = None) -> Any:
        """Close WebSocket connection."""
        await self.websocket.close(code=code, reason=reason)

    @property
    def client_state(self) -> Any:
        """Get WebSocket client state."""
        return self.websocket.client_state

    @property
    def application_state(self) -> Any:
        """Get WebSocket application state."""
        return self.websocket.application_state


__all__ = [
    "GuardedWebSocket",
    "execute_websocket_guards",
]
