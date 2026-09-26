"""WebSocket message handler registry for event streaming."""

from __future__ import annotations

from typing import Any, Protocol

from quadkit.events.constants import WebSocketMessageType


class WSMessageHandler(Protocol):
    """Protocol for WebSocket message handlers."""

    def can_handle(self, message_type: str | None) -> bool:
        """Check if this handler can handle the message type."""
        ...

    async def handle_message(
        self,
        stream: Any,
        connection: Any,
        message: dict[str, Any],
    ) -> None:
        """Handle the WebSocket message."""
        ...


class SubscribeMessageHandler:
    """Handler for subscribe messages."""

    def can_handle(self, message_type: str | None) -> bool:
        return message_type == WebSocketMessageType.SUBSCRIBE

    async def handle_message(
        self,
        stream: Any,
        connection: Any,
        message: dict[str, Any],
    ) -> None:
        await stream._handle_subscribe(connection, message)


class UnsubscribeMessageHandler:
    """Handler for unsubscribe messages."""

    def can_handle(self, message_type: str | None) -> bool:
        return message_type == WebSocketMessageType.UNSUBSCRIBE

    async def handle_message(
        self,
        stream: Any,
        connection: Any,
        message: dict[str, Any],
    ) -> None:
        await stream._handle_unsubscribe(connection, message)


class PingMessageHandler:
    """Handler for ping messages."""

    def can_handle(self, message_type: str | None) -> bool:
        return message_type == WebSocketMessageType.PING

    async def handle_message(
        self,
        stream: Any,
        connection: Any,
        message: dict[str, Any],
    ) -> None:
        await stream._send_message(
            connection,
            {"type": WebSocketMessageType.PONG},
        )


class WSMessageHandlerRegistry:
    """Central registry for WebSocket message handlers."""

    def __init__(self) -> None:
        self._handlers: list[WSMessageHandler] = []

    @classmethod
    def _default_entries(cls) -> dict[str, WSMessageHandler]:
        """Declare the built-in default handlers (subscribe, unsubscribe, ping)."""
        return {
            "subscribe": SubscribeMessageHandler(),
            "unsubscribe": UnsubscribeMessageHandler(),
            "ping": PingMessageHandler(),
        }

    @classmethod
    def with_defaults(cls) -> WSMessageHandlerRegistry:
        """Create a registry pre-populated with the built-in default handlers."""
        registry = cls()
        registry._handlers = list(cls._default_entries().values())
        return registry

    def register(self, handler: WSMessageHandler) -> None:
        """Register a new message handler."""
        self._handlers.insert(0, handler)

    async def handle_message(
        self,
        stream: Any,
        connection: Any,
        message: dict[str, Any],
    ) -> bool:
        """Handle message using the appropriate handler. Returns True if handled."""
        msg_type = message.get("type")
        for handler in self._handlers:
            if handler.can_handle(msg_type):
                await handler.handle_message(stream, connection, message)
                return True
        return False


_ws_message_handler_registry = WSMessageHandlerRegistry.with_defaults()


def get_ws_message_handler_registry(
    context: Any | None = None,
) -> WSMessageHandlerRegistry:
    """Get the global WebSocket message handler registry."""
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(context)
    if resolver:
        registry: WSMessageHandlerRegistry = resolver.resolve_sync(
            WSMessageHandlerRegistry
        )
        return registry

    return _ws_message_handler_registry
