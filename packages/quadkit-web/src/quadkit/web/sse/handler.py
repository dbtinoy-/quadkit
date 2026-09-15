"""SSE Handler Base Class.

Provides an abstract base class for Server-Sent Events handlers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from collections.abc import AsyncGenerator
from typing import Any, ClassVar

from starlette.requests import Request

from quadkit.logging import get_logger
from quadkit.web.exceptions import TooManyConnectionsError

logger = get_logger(__name__)
from quadkit.web.transport.sse import EventSourceResponse, ServerSentEvent


class AbstractSSEHandler(ABC):
    """Base class for SSE handlers.

    Subclass this to create SSE endpoints with automatic event streaming,
    heartbeat support, and connection management.

    Attributes:
        heartbeat_interval: Seconds between heartbeat events (default: 30)
        retry: Client retry interval in milliseconds (default: 3000)
        event_types: List of supported event types for documentation

    Example:
        ```python
        @sse_endpoint("/events/{channel}")
        class ChannelEventsHandler(AbstractSSEHandler):
            heartbeat_interval = 15
            event_types = ["message", "join", "leave"]

            async def stream(self, request):
                channel = request.path_params["channel"]
                async for event in channel_events(channel):
                    yield {"event": "message", "data": event}
        ```
    """

    # Configuration
    heartbeat_interval: int = 30
    retry: int = 3000
    event_types: ClassVar[list[str]] = []
    max_connections: ClassVar[int] = 0  # 0 = unlimited

    # Connection tracking (class-level, shared across instances)
    _active_connections: ClassVar[int] = 0
    _connection_lock: ClassVar[asyncio.Lock | None] = None
    _connections: set[Request]

    # Route metadata (set by decorator)
    _path: str | None = None
    _guards: ClassVar[list[Any]] = []

    def __init__(self) -> None:
        self._connections = set()

    @classmethod
    def _get_connection_lock(cls) -> asyncio.Lock:
        """Return the per-class asyncio lock, creating it lazily on first call.

        Each concrete subclass gets its own lock so different handler types
        track their connections independently.
        """
        if cls._connection_lock is None:
            cls._connection_lock = asyncio.Lock()
        return cls._connection_lock

    @abstractmethod
    async def stream(self, request: Request) -> AsyncGenerator[dict[str, Any], None]:
        """Generate SSE events.

        Override this method to yield events to the client.

        Args:
            request: The incoming HTTP request

        Yields:
            Dict with 'event' (optional), 'data', 'id' (optional), 'retry' (optional)
        """
        yield {}  # pragma: no cover

    async def on_connect(self, request: Request) -> None:
        """Called when a client connects.

        Override to perform setup when a client starts streaming.

        Args:
            request: The incoming HTTP request
        """

    async def on_disconnect(self, request: Request) -> None:
        """Called when a client disconnects.

        Override to perform cleanup when a client stops streaming.

        Args:
            request: The incoming HTTP request
        """

    async def add(self, connection: Request) -> None:
        """Register a connection (satisfies :class:`ConnectionManagerProtocol`)."""
        async with type(self)._get_connection_lock():
            self._connections.add(connection)
            type(self)._active_connections += 1

    async def remove(self, connection: Request) -> None:
        """Unregister a connection (satisfies :class:`ConnectionManagerProtocol`)."""
        async with type(self)._get_connection_lock():
            self._connections.discard(connection)
            type(self)._active_connections -= 1

    async def broadcast(self, message: Any, exclude: Request | None = None) -> None:
        """Broadcast is not supported for SSE connections.

        SSE is a unidirectional protocol — each client has its own event
        generator.  Override :meth:`stream` and use a shared async queue
        or pub/sub channel to push events to multiple clients.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(
            "SSE broadcast requires a shared event source; "
            "use a pub/sub channel or async queue in your stream() implementation"
        )

    @property
    def count(self) -> int:
        """Return the number of active connections."""
        return type(self)._active_connections

    async def _create_event_generator(
        self,
        request: Request,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        """Internal: Create the SSE event generator with heartbeat support."""
        try:
            await self.on_connect(request)

            # Initial retry instruction
            if self.retry:
                yield ServerSentEvent(data="", retry=self.retry)

            # Simple approach: yield from stream with periodic heartbeat
            last_heartbeat = asyncio.get_running_loop().time()

            async for event_data in self.stream(request):
                # Check if heartbeat is due
                now = asyncio.get_running_loop().time()
                if now - last_heartbeat >= self.heartbeat_interval:
                    yield ServerSentEvent(data="", event="heartbeat")
                    last_heartbeat = now

                # Yield the actual event
                yield ServerSentEvent(
                    data=event_data.get("data", event_data),
                    event=event_data.get("event"),
                    event_id=event_data.get("id"),
                    retry=event_data.get("retry"),
                )
        finally:
            try:
                await self.on_disconnect(request)
            except Exception as exc:  # noqa: BLE001 — disconnect is best-effort; must not mask stream errors
                logger.debug("sse_on_disconnect_failed", error=str(exc))

    def create_event(
        self,
        event_type: str,
        data: Any,
        event_id: str | None = None,
    ) -> dict[str, Any]:
        """Helper to create an event dict.

        Args:
            event_type: The event type name
            data: Event payload
            event_id: Optional event ID for client tracking

        Returns:
            Dict suitable for yielding from stream()
        """
        result = {"event": event_type, "data": data}
        if event_id:
            result["id"] = event_id
        return result

    async def handle(self, request: Request) -> EventSourceResponse:
        """Handle an SSE request.

        Checks ``max_connections`` before accepting; raises
        ``TooManyConnectionsError`` (503) if the cap is reached.
        Decrements the active connection count when the response stream closes.

        Args:
            request: The incoming HTTP request

        Returns:
            EventSourceResponse streaming events to the client
        """
        async with type(self)._get_connection_lock():
            if (
                self.max_connections > 0
                and type(self)._active_connections >= self.max_connections
            ):
                raise TooManyConnectionsError(
                    f"SSE connection limit reached ({self.max_connections})"
                )
            # Register directly under the lock to keep the limit-check and
            # increment atomic.  Intentionally bypasses add() to avoid
            # re-acquiring _connection_lock (asyncio.Lock is not reentrant).
            self._connections.add(request)
            type(self)._active_connections += 1

        async def _guarded_generator() -> AsyncGenerator[ServerSentEvent, None]:
            try:
                async for event in self._create_event_generator(request):
                    yield event
            finally:
                await self.remove(request)

        return EventSourceResponse(_guarded_generator())


__all__ = ["AbstractSSEHandler"]
