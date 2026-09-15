"""WebSocket Gateway — declarative event-driven WebSocket handling.

Introduces a higher-level ``WebSocketGateway`` base class and companion
decorators that replace manual ``if/elif`` dispatch inside ``on_message``
with a registry-based, type-safe event routing system.

Example::

    from quadkit.web.websocket.gateway import (
        WebSocketGateway,
        on_connect,
        subscribe_message,
        websocket_gateway,
    )

    @websocket_gateway("/ws/chat")
    class ChatGateway(WebSocketGateway):

        def __init__(self, rooms: RoomManager) -> None:
            super().__init__()
            self.rooms = rooms   # DI-resolved

        @subscribe_message("chat.send")
        async def handle_send(self, websocket: WebSocket, payload: dict) -> None:
            await self.rooms.broadcast(payload)

        @subscribe_message("room.join")
        async def handle_join(self, websocket: WebSocket, payload: dict) -> None:
            await self.rooms.join(payload.get("room"), websocket)

        @on_connect
        async def connected(self, websocket: WebSocket) -> None:
            await websocket.accept()
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.logging import get_logger
from quadkit.web.websocket.handler import AbstractWebSocketHandler

if TYPE_CHECKING:
    from quadkit.web.transport.websockets import WebSocket

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# Sentinel attribute names written onto decorated methods
_SUBSCRIBE_MESSAGE_ATTR = "__ws_subscribe_message__"
_ON_CONNECT_ATTR = "__ws_on_connect__"
_ON_DISCONNECT_ATTR = "__ws_on_disconnect__"
_ON_ERROR_ATTR = "__ws_on_error__"


def subscribe_message(event_type: str) -> Callable[[F], F]:
    """Mark a gateway method as the handler for a specific message type.

    The method will be called automatically when an incoming message's
    ``"type"`` field (or top-level key) matches ``event_type``.

    Args:
        event_type: The message type string to match (e.g. ``"chat.send"``).

    Example::

        @subscribe_message("chat.send")
        async def handle_send(self, websocket: WebSocket, payload: dict) -> None:
            ...
    """

    def decorator(fn: F) -> F:
        existing: list[str] = getattr(fn, _SUBSCRIBE_MESSAGE_ATTR, [])
        fn.__ws_subscribe_message__ = [*existing, event_type]  # type: ignore[attr-defined]
        return fn

    return decorator


def on_connect(fn: F) -> F:
    """Mark a gateway method as the connection handler.

    The decorated method replaces ``on_connect`` in :class:`AbstractWebSocketHandler`.
    Only one ``@on_connect`` method per gateway is allowed.

    Args:
        fn: The async method to call on connection.
    """
    fn.__ws_on_connect__ = True  # type: ignore[attr-defined]
    return fn


def on_disconnect(fn: F) -> F:
    """Mark a gateway method as the disconnection handler.

    Args:
        fn: The async method to call upon disconnection.
    """
    fn.__ws_on_disconnect__ = True  # type: ignore[attr-defined]
    return fn


def on_error(fn: F) -> F:
    """Mark a gateway method as the error handler.

    Args:
        fn: The async method to call when an error occurs.
    """
    fn.__ws_on_error__ = True  # type: ignore[attr-defined]
    return fn


class WebSocketGateway(AbstractWebSocketHandler):
    """High-level declarative WebSocket gateway.

    Extend this class and use :func:`subscribe_message`, :func:`on_connect`,
    and :func:`on_disconnect` decorators to define event handlers.  The
    gateway automatically dispatches incoming messages to the correct method
    based on the ``"type"`` field of the received JSON payload.

    If no specific handler matches, the default ``on_unhandled_message``
    method is called (no-op by default; override to customise).

    DI works naturally — declare constructor parameters, and the container
    will inject dependencies when the gateway is resolved::

        @websocket_gateway("/ws/chat")
        class ChatGateway(WebSocketGateway):

            def __init__(self, rooms: RoomManager) -> None:
                super().__init__()
                self.rooms = rooms

            @subscribe_message("chat.send")
            async def handle_send(self, ws: WebSocket, payload: dict) -> None:
                await self.rooms.broadcast(payload)
    """

    _message_registry: dict[str, Callable[..., Any]] = {}
    _connect_handler: Callable[..., Any] | None = None
    _disconnect_handler: Callable[..., Any] | None = None
    _error_handler: Callable[..., Any] | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Build the message dispatch registry for this subclass
        registry: dict[str, Callable[..., Any]] = {}
        connect_handler: Callable[..., Any] | None = None
        disconnect_handler: Callable[..., Any] | None = None
        error_handler: Callable[..., Any] | None = None

        for name in dir(cls):
            try:
                method = getattr(cls, name)
            except AttributeError:
                continue

            # Message subscriptions — a method can handle multiple event types
            subscriptions: list[str] = getattr(method, _SUBSCRIBE_MESSAGE_ATTR, [])
            for event_type in subscriptions:
                if event_type in registry:
                    logger.warning(
                        "Duplicate @subscribe_message handler for type %r in %s",
                        event_type,
                        cls.__name__,
                    )
                registry[event_type] = method

            if getattr(method, _ON_CONNECT_ATTR, False):
                connect_handler = method
            if getattr(method, _ON_DISCONNECT_ATTR, False):
                disconnect_handler = method
            if getattr(method, _ON_ERROR_ATTR, False):
                error_handler = method

        cls._message_registry = registry
        cls._connect_handler = connect_handler
        cls._disconnect_handler = disconnect_handler
        cls._error_handler = error_handler

    def __init__(self) -> None:
        super().__init__()
        # Ensure per-instance registry copy so subclass attributes shadow safely
        self._message_registry = dict(type(self)._message_registry)

    async def on_connect(self, websocket: WebSocket) -> None:
        """Routes to the @on_connect decorated method, or accepts by default."""
        connect = type(self)._connect_handler
        if connect is not None:
            await connect(self, websocket)
        else:
            # Safe default — accept and continue
            await websocket.accept()

    async def on_disconnect(self, websocket: WebSocket) -> None:
        """Routes to the @on_disconnect decorated method, or no-ops."""
        disconnect = type(self)._disconnect_handler
        if disconnect is not None:
            await disconnect(self, websocket)

    async def on_error(self, websocket: WebSocket, error: Exception) -> None:
        """Routes to the @on_error decorated method, or uses default handling."""
        error_h = type(self)._error_handler
        if error_h is not None:
            await error_h(self, websocket, error)
        else:
            await super().on_error(websocket, error)

    async def on_message(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Dispatch incoming message to the correct @subscribe_message handler.

        Looks up the ``"type"`` field of the message in the registry.
        If no match is found, ``on_unhandled_message`` is called.

        Args:
            websocket: The WebSocket connection.
            message: The received JSON payload (already parsed).
        """
        event_type = message.get("type") or message.get("event")
        if event_type is None:
            await self.on_unhandled_message(websocket, message)
            return

        handler = self._message_registry.get(str(event_type))
        if handler is None:
            logger.debug("No handler for WebSocket event %r", event_type)
            await self.on_unhandled_message(websocket, message)
            return

        # Strip the "type" key from the payload before passing to the handler
        payload = {k: v for k, v in message.items() if k not in ("type", "event")}
        await handler(self, websocket, payload)

    async def on_unhandled_message(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        """Called when no handler matches the incoming message type.

        Override to customise the behaviour. Default sends an error response.

        Args:
            websocket: The WebSocket connection.
            message: The unhandled message.
        """
        event_type = message.get("type") or message.get("event") or "unknown"
        await self.send_error(websocket, f"Unhandled event: {event_type}")


def websocket_gateway(
    path: str,
    *,
    ping_interval: int | None = None,
    ping_timeout: int | None = None,
    max_connections_per_user: int | None = None,
) -> Callable[[type], type]:
    """Mark a class as a WebSocket gateway endpoint.

    This is the high-level companion to :func:`quadkit.web.websocket.decorators.websocket_handler`.
    Use it together with :class:`WebSocketGateway`.

    Args:
        path: URL path for the WebSocket endpoint (may include path params).
        ping_interval: Override default keepalive ping interval (seconds).
        ping_timeout: Override default pong timeout (seconds).
        max_connections_per_user: Limit concurrent connections per user.

    Example::

        @websocket_gateway("/ws/notifications")
        class NotificationGateway(WebSocketGateway):
            ...
    """

    def decorator(cls: type) -> type:
        if ping_interval is not None:
            cls.ping_interval = ping_interval  # type: ignore[attr-defined]
        if ping_timeout is not None:
            cls.ping_timeout = ping_timeout  # type: ignore[attr-defined]
        if max_connections_per_user is not None:
            cls.max_connections_per_user = max_connections_per_user  # type: ignore[attr-defined]

        cls._ws_path = path  # type: ignore[attr-defined]
        cls._ws_metadata = {  # type: ignore[attr-defined]
            "path": path,
            "ping_interval": ping_interval,
            "ping_timeout": ping_timeout,
            "max_connections_per_user": max_connections_per_user,
        }
        cls._is_websocket_handler = True  # type: ignore[attr-defined]
        cls._is_websocket_gateway = True  # type: ignore[attr-defined]
        return cls

    return decorator


__all__ = [
    "WebSocketGateway",
    "on_connect",
    "on_disconnect",
    "on_error",
    "subscribe_message",
    "websocket_gateway",
]
