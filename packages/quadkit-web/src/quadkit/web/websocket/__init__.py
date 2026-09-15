"""WebSocket Module.

Provides base classes and decorators for building WebSocket handlers
and gateways.

Low-level handler example::

    from quadkit.web.websocket import AbstractWebSocketHandler, websocket_handler

    @websocket_handler("/ws/chat/{room}")
    class ChatHandler(AbstractWebSocketHandler):
        async def on_connect(self, websocket):
            await websocket.accept()
        async def on_message(self, websocket, message):
            await self.broadcast(message)
        async def on_disconnect(self, websocket):
            pass

High-level gateway example::

    from quadkit.web.websocket import WebSocketGateway, subscribe_message, websocket_gateway

    @websocket_gateway("/ws/chat")
    class ChatGateway(WebSocketGateway):
        @subscribe_message("chat.send")
        async def handle_send(self, ws, payload):
            await self.broadcast(payload)
"""

from __future__ import annotations

from quadkit.web.transport.websocket_guards import (
    GuardedWebSocket,
    execute_websocket_guards,
)
from quadkit.web.transport.websockets import WebSocket
from quadkit.web.websocket.connection_id import ConnectionIDManager
from quadkit.web.websocket.decorators import websocket_handler
from quadkit.web.websocket.gateway import (
    WebSocketGateway,
    on_connect,
    on_disconnect,
    on_error,
    subscribe_message,
    websocket_gateway,
)
from quadkit.web.websocket.handler import AbstractWebSocketHandler
from quadkit.web.websocket.rate_limiter import WebSocketRateLimiter

__all__ = [
    "AbstractWebSocketHandler",
    "ConnectionIDManager",
    "GuardedWebSocket",
    "WebSocket",
    "WebSocketGateway",
    "WebSocketRateLimiter",
    "execute_websocket_guards",
    "on_connect",
    "on_disconnect",
    "on_error",
    "subscribe_message",
    "websocket_gateway",
    "websocket_handler",
]
