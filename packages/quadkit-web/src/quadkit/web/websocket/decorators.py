"""WebSocket Decorators.

Provides decorators for marking classes as WebSocket handlers.
"""

from __future__ import annotations

from typing import Any, cast


def websocket_handler(
    path: str,
    *,
    ping_interval: int | None = None,
    ping_timeout: int | None = None,
    max_connections_per_user: int | None = None,
) -> Any:
    """Decorator to mark a class as a WebSocket handler.

    This decorator registers the handler class with the router
    and configures the WebSocket path.

    Args:
        path: URL path for the WebSocket endpoint (can include path parameters)
        ping_interval: Override default ping interval
        ping_timeout: Override default ping timeout
        max_connections_per_user: Override max connections per user

    Example:
        ```python
        @websocket_handler("/ws/chat/{room}")
        class ChatHandler(AbstractWebSocketHandler):
            async def on_connect(self, websocket):
                await websocket.accept()
                await self.broadcast({"type": "join", "user": "..."})

            async def on_message(self, websocket, message):
                await self.broadcast(message)

            async def on_disconnect(self, websocket):
                await self.broadcast({"type": "leave", "user": "..."})
        ```
    """

    def decorator(cls: type) -> type:
        # Store route metadata on the class using setattr to satisfy mypy
        cast("Any", cls)._ws_path = path
        cast("Any", cls)._ws_metadata = {
            "path": path,
            "ping_interval": ping_interval,
            "ping_timeout": ping_timeout,
            "max_connections_per_user": max_connections_per_user,
        }

        # Override class attributes if provided
        if ping_interval is not None:
            cast("Any", cls).ping_interval = ping_interval
        if ping_timeout is not None:
            cast("Any", cls).ping_timeout = ping_timeout
        if max_connections_per_user is not None:
            cast("Any", cls).max_connections_per_user = max_connections_per_user

        # Mark as WebSocket handler for router discovery
        cast("Any", cls)._is_websocket_handler = True

        return cls

    return decorator


__all__ = ["websocket_handler"]
