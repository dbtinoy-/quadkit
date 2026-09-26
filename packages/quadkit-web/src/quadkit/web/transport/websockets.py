"""WebSocket support"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from starlette.websockets import WebSocket as StarletteWebSocket


class WebSocket:
    """Quadkit WebSocket wrapper around Starlette WebSocket"""

    def __init__(self, starlette_ws: StarletteWebSocket):
        self._starlette = starlette_ws

    async def accept(self, subprotocol: str | None = None) -> None:
        await self._starlette.accept(subprotocol=subprotocol)

    async def close(self, code: int = 1000) -> None:
        await self._starlette.close(code=code)

    async def receive_text(self) -> str:
        return await self._starlette.receive_text()

    async def receive_json(self) -> Any:
        return await self._starlette.receive_json()

    async def receive_event(self) -> MutableMapping[str, Any]:
        """Receive a raw ASGI WebSocket event for protocol bridges.

        Starlette types the ASGI message as a mutable mapping, not a plain
        ``dict``; declaring the wider type is what keeps ``make type`` honest
        without an unchecked cast.
        """
        return await self._starlette.receive()

    @property
    def headers(self) -> Any:
        """Handshake headers exposed read-only to gateway handlers."""
        return self._starlette.headers

    @property
    def query_params(self) -> Any:
        """Handshake query parameters exposed to gateway handlers."""
        return self._starlette.query_params

    async def send_text(self, data: str) -> None:
        await self._starlette.send_text(data)

    async def send_json(self, data: Any) -> None:
        await self._starlette.send_json(data)

    async def send_bytes(self, data: bytes) -> None:
        await self._starlette.send_bytes(data)

    @property
    def state(self) -> Any:
        """WebSocket state for middleware."""
        return self._starlette.state

    @property
    def path_params(self) -> dict[str, Any]:
        """Path parameters captured by the Starlette WebSocket route."""
        return dict(self._starlette.path_params)
