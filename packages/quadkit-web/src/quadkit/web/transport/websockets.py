"""WebSocket support"""

from __future__ import annotations

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
