"""Outbound WebSocket transport built on QuadKit HTTP dependencies.

The transport deliberately exposes a small protocol-neutral surface so gateway
modules can bridge WebSockets without importing an ASGI or provider-specific
client. HTTP applications use the same aiohttp connection stack as the rest of
``quadkit-http``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp


@dataclass(frozen=True)
class WebSocketMessage:
    """A normalized message received from an outbound WebSocket."""

    type: str
    data: Any = None


class WebSocketClient:
    """Async context-managed outbound WebSocket client."""

    def __init__(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        connect_timeout: float = 30.0,
        heartbeat: float | None = 30.0,
    ) -> None:
        if not url.startswith(("ws://", "wss://")):
            raise ValueError("WebSocket URL must start with ws:// or wss://")
        self.url = url
        self.headers = headers or {}
        self.connect_timeout = connect_timeout
        self.heartbeat = heartbeat
        self._session: aiohttp.ClientSession | None = None
        self._socket: aiohttp.ClientWebSocketResponse | None = None

    async def __aenter__(self) -> WebSocketClient:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=None, sock_connect=self.connect_timeout)
        )
        try:
            self._socket = await self._session.ws_connect(
                self.url,
                headers=self.headers,
                heartbeat=self.heartbeat,
                autoping=True,
            )
        except BaseException:
            await self._session.close()
            self._session = None
            raise
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.close()

    @property
    def closed(self) -> bool:
        """Whether the upstream connection has closed."""
        return self._socket is None or self._socket.closed

    async def send_json(self, payload: Any) -> None:
        """Send one JSON event."""
        if self._socket is None:
            raise RuntimeError("WebSocketClient is not connected")
        await self._socket.send_json(payload)

    async def send_text(self, payload: str) -> None:
        """Send one text frame."""
        if self._socket is None:
            raise RuntimeError("WebSocketClient is not connected")
        await self._socket.send_str(payload)

    async def send_bytes(self, payload: bytes) -> None:
        """Send one binary frame."""
        if self._socket is None:
            raise RuntimeError("WebSocketClient is not connected")
        await self._socket.send_bytes(payload)

    async def receive(self) -> WebSocketMessage:
        """Receive and normalize one upstream frame."""
        if self._socket is None:
            raise RuntimeError("WebSocketClient is not connected")
        message = await self._socket.receive()
        message_type = message.type
        if message_type is aiohttp.WSMsgType.TEXT:
            return WebSocketMessage("text", message.data)
        if message_type is aiohttp.WSMsgType.BINARY:
            return WebSocketMessage("bytes", message.data)
        if message_type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
            return WebSocketMessage("close", message.data)
        if message_type is aiohttp.WSMsgType.ERROR:
            return WebSocketMessage("error", str(message.data))
        # Ping/pong frames are handled by aiohttp's autoping. Expose them as
        # control messages for callers that need explicit protocol telemetry.
        return WebSocketMessage(str(message_type).lower(), message.data)

    async def close(self) -> None:
        """Close the WebSocket and its HTTP session."""
        if self._socket is not None and not self._socket.closed:
            await self._socket.close()
        self._socket = None
        if self._session is not None:
            await self._session.close()
        self._session = None


__all__ = ["WebSocketClient", "WebSocketMessage"]
