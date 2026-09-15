"""WebSocket Handler Base Class.

Guidance — Handler vs Gateway
------------------------------

:class:`AbstractWebSocketHandler` is for **application-level WebSocket endpoints** that
are owned and processed by the current Quadkit application:

- Chat rooms, live dashboards, notifications, collaborative editing
- When the connection logic (auth, rooms, broadcast) lives *in this app*
- Each handler class maps to one URL pattern

**When to use a WebSocket Gateway instead:**

A gateway (reverse-proxy pattern) is appropriate when the Quadkit application
acts as a *protocol translator or hub* rather than the final consumer:

- Proxying WebSocket connections to a backend service
- Multiplexing many logical channels over one underlying connection
- Bridging WebSocket↔AMQP/Redis Pub-Sub

In those cases, do not use :class:`AbstractWebSocketHandler` — use a raw ASGI handler
or the messaging layer (:mod:`quadkit.messaging`) with a pub/sub backend.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from starlette.websockets import WebSocketDisconnect

from quadkit import serialization as json
from quadkit.logging import get_logger
from quadkit.web.transport.websockets import WebSocket
from quadkit.web.websocket.connection_id import ConnectionIDManager
from quadkit.web.websocket.rate_limiter import WebSocketRateLimiter

logger = get_logger(__name__)


class AbstractWebSocketHandler(ABC):
    """Base class for WebSocket handlers.

    Subclass this to create WebSocket endpoints with connection lifecycle
    management, message handling, and optional room/broadcast support.

    Attributes:
        ping_interval: Seconds between ping frames (default: 30)
        ping_timeout: Seconds to wait for pong response (default: 10)
        max_connections: Global cap on concurrent connections for this handler.
            New connections are rejected when the cap is reached (default: None).
        max_connections_per_user: Limit concurrent connections per user identity.
            Requires ``get_user_id()`` to return a non-None value (default: None).
        max_messages_per_second: Per-connection message rate limit using a
            token-bucket algorithm (default: None — unlimited).

    Example:
        ```python
        @websocket_handler("/ws/chat/{room_id}")
        class ChatHandler(AbstractWebSocketHandler):
            rooms: dict[str, set[WebSocket]] = {}

            async def on_connect(self, websocket):
                room_id = websocket.path_params["room_id"]
                if room_id not in self.rooms:
                    self.rooms[room_id] = set()
                self.rooms[room_id].add(websocket)
                await websocket.accept()

            async def on_message(self, websocket, message):
                room_id = websocket.path_params["room_id"]
                for ws in self.rooms.get(room_id, []):
                    await ws.send_json(message)

            async def on_disconnect(self, websocket):
                room_id = websocket.path_params["room_id"]
                self.rooms.get(room_id, set()).discard(websocket)
        ```
    """

    # Configuration
    ping_interval: int = 30
    ping_timeout: int = 10
    max_connections: int | None = None
    max_connections_per_user: int | None = None
    max_messages_per_second: float | None = None

    # Route metadata (set by decorator)
    _path: str | None = None
    _guards: ClassVar[list[Any]] = []

    # Connection tracking
    _connections: set[WebSocket]

    def __init__(
        self,
        connection_id_manager: ConnectionIDManager | None = None,
    ) -> None:
        self._connections = set()
        # Per-user connection count tracking: user_id → set of connection UUIDs
        self._user_connections: dict[str, set[str]] = {}
        self._connection_id_manager = (
            connection_id_manager
            if connection_id_manager is not None
            else ConnectionIDManager()
        )
        self._rate_limiter: WebSocketRateLimiter | None = (
            WebSocketRateLimiter(self.max_messages_per_second)
            if self.max_messages_per_second is not None
            else None
        )

    @abstractmethod
    async def on_connect(self, websocket: WebSocket) -> None:
        """Called when a client connects.

        Override to handle connection setup. You MUST call
        `await websocket.accept()` to accept the connection.

        Args:
            websocket: The WebSocket connection
        """

    @abstractmethod
    async def on_message(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        """Called when a message is received.

        Override to handle incoming messages.

        Args:
            websocket: The WebSocket connection
            message: The parsed JSON message
        """
        # pragma: no cover

    @abstractmethod
    async def on_disconnect(self, websocket: WebSocket) -> None:
        """Called when a client disconnects.

        Override to handle cleanup.

        Args:
            websocket: The WebSocket connection
        """
        # pragma: no cover

    async def on_error(self, websocket: WebSocket, error: Exception) -> None:
        """Called when an error occurs.

        Override to handle errors. Default implementation logs and closes.

        Args:
            websocket: The WebSocket connection
            error: The exception that occurred
        """
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": str(error),
                },
            )
        except (RuntimeError, ConnectionError, OSError, AttributeError):
            # Log and swallow to avoid crashing the WebSocket handler for operational errors
            logger.exception("Failed to send error message to websocket")

    async def send_json(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """Send JSON data to a websocket.

        Args:
            websocket: The WebSocket connection
            data: Data to send as JSON
        """
        await websocket.send_json(data)

    async def send_text(self, websocket: WebSocket, text: str) -> None:
        """Send text data to a websocket.

        Args:
            websocket: The WebSocket connection
            text: Text to send
        """
        await websocket.send_text(text)

    async def send_error(self, websocket: WebSocket, error: str) -> None:
        """Send an error message to a websocket.

        Args:
            websocket: The WebSocket connection
            error: Error message
        """
        await websocket.send_json({"type": "error", "error": error})

    async def broadcast(
        self,
        message: dict[str, Any],
        exclude: WebSocket | None = None,
    ) -> None:
        """Broadcast message to all connected clients.

        Args:
            message: Message to broadcast
            exclude: Optional WebSocket to exclude from broadcast
        """
        for ws in self._connections:
            if ws != exclude:
                try:
                    await ws.send_json(message)
                except Exception:  # noqa: BLE001 — one dead connection must not stop the remaining broadcasts
                    logger.exception(
                        "Error broadcasting JSON message to websocket client",
                    )

    async def broadcast_text(
        self,
        text: str,
        exclude: WebSocket | None = None,
    ) -> None:
        """Broadcast text to all connected clients.

        Args:
            text: Text to broadcast
            exclude: Optional WebSocket to exclude from broadcast
        """
        for ws in self._connections:
            if ws != exclude:
                try:
                    await ws.send_text(text)
                except Exception:  # noqa: BLE001 — one dead connection must not stop the remaining broadcasts
                    logger.exception(
                        "Error broadcasting text message to websocket client",
                    )

    @property
    def connection_count(self) -> int:
        """Get current number of connections."""
        return len(self._connections)

    @property
    def count(self) -> int:
        """Alias for :attr:`connection_count` (satisfies :class:`ConnectionManagerProtocol`)."""
        return len(self._connections)

    async def add(self, connection: WebSocket) -> None:
        """Register a connection.

        Called automatically during :meth:`handle`.  Can also be called
        directly when managing connections outside the default loop.
        """
        self._connections.add(connection)

    async def remove(self, connection: WebSocket) -> None:
        """Unregister a connection.

        Called automatically during :meth:`handle`.  Can also be called
        directly when managing connections outside the default loop.
        """
        self._connections.discard(connection)

    def get_user_id(self, websocket: WebSocket) -> str | None:
        """Return a stable identifier for the connecting user.

        Override this method to enable ``max_connections_per_user``
        enforcement.  The default implementation checks for a ``user``
        attribute on ``websocket.state`` (commonly set by authentication
        middleware) and falls back to ``None`` (enforcement disabled).

        Args:
            websocket: The incoming WebSocket connection (before accept).

        Returns:
            A hashable string user identifier, or ``None`` to skip
            per-user limit enforcement for this connection.
        """
        state = getattr(websocket, "state", None)
        user = getattr(state, "user", None) if state is not None else None
        if user is None:
            return None
        return str(getattr(user, "id", None) or getattr(user, "sub", None) or str(user))

    async def handle(self, websocket: WebSocket) -> None:
        """Handle a WebSocket connection.

        This is called by the router to process the WebSocket.
        It manages the connection lifecycle and message loop.

        Args:
            websocket: The WebSocket connection
        """
        # --- Connection-level rate limiting (before accept) ---

        # Global connection cap
        if (
            self.max_connections is not None
            and len(self._connections) >= self.max_connections
        ):
            logger.warning(
                "websocket.connection_limit_reached",
                max_connections=self.max_connections,
                current=len(self._connections),
            )
            await websocket.close(code=1008, reason="connection_limit_exceeded")  # type: ignore[call-arg]
            return

        # Per-user connection cap
        user_id: str | None = None
        if self.max_connections_per_user is not None:
            user_id = self.get_user_id(websocket)
            if user_id is not None:
                user_conn_ids = self._user_connections.get(user_id, set())
                if len(user_conn_ids) >= self.max_connections_per_user:
                    logger.warning(
                        "websocket.user_connection_limit_reached",
                        user_id=user_id,
                        max_connections_per_user=self.max_connections_per_user,
                    )
                    await websocket.close(
                        code=1008, reason="user_connection_limit_exceeded"
                    )  # type: ignore[call-arg]
                    return

        try:
            # Register connection before on_connect so broadcast includes it
            await self.add(websocket)
            if user_id is not None:
                connection_uuid = self._connection_id_manager.get_or_create(websocket)  # type: ignore[arg-type]
                self._user_connections.setdefault(user_id, set()).add(connection_uuid)

            # Call on_connect - user must call accept()
            await self.on_connect(websocket)

            # Message loop
            while True:
                try:
                    # Receive message
                    data = await websocket.receive_json()

                    # Enforce per-connection rate limit if configured
                    if self._rate_limiter is not None:
                        connection_uuid = self._connection_id_manager.get_or_create(
                            websocket  # type: ignore[arg-type]
                        )
                        if not await self._rate_limiter.check(connection_uuid):
                            await self.send_error(websocket, "rate_limit_exceeded")
                            continue

                    await self.on_message(websocket, data)
                except json.JSONDecodeError as e:
                    await self.on_error(websocket, e)
                except WebSocketDisconnect:
                    # Client disconnected, stop the loop gracefully
                    break
                except (RuntimeError, ConnectionError, OSError):
                    # Connection closed or other operational error; log and stop the loop
                    logger.exception(
                        "Error while receiving messages from websocket; closing connection",
                    )
                    break

        except Exception as e:  # noqa: BLE001 — websocket handler must catch any error to invoke on_error and clean up the connection
            logger.exception("Unhandled websocket handler error")
            await self.on_error(websocket, e)
        finally:
            await self.remove(websocket)
            # Clean up per-user tracking
            if user_id is not None and user_id in self._user_connections:
                connection_uuid = self._connection_id_manager.get(websocket)  # type: ignore[arg-type,assignment]
                if connection_uuid is not None:
                    self._user_connections[user_id].discard(connection_uuid)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]
            if self._rate_limiter is not None:
                connection_uuid = self._connection_id_manager.get(websocket)  # type: ignore[arg-type,assignment]
                if connection_uuid is not None:
                    await self._rate_limiter.remove(connection_uuid)
            try:
                await self.on_disconnect(websocket)
            except Exception:  # noqa: BLE001 — disconnect is best-effort; must not mask the connection error
                logger.exception("Error during websocket disconnect handler")


__all__ = ["AbstractWebSocketHandler"]
