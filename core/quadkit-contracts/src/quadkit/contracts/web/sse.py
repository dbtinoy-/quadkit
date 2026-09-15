"""Server-Sent Events (SSE) contracts.

Defines the data transfer types and factory protocol for Server-Sent Events
so that packages outside of ``quadkit-web`` can produce SSE responses without
creating a cross-extension dependency.

Usage::

    from quadkit.contracts.web.sse import ServerSentEvent, SseResponseFactoryProtocol

    async def my_handler(
        factory: SseResponseFactoryProtocol,
        event_generator: AsyncGenerator[dict[str, Any], None],
    ) -> Any:
        async def wrapped():
            async for event_data in event_generator:
                yield ServerSentEvent(
                    data=event_data.get("data", event_data),
                    event=event_data.get("event"),
                    event_id=event_data.get("id"),
                    retry=event_data.get("retry"),
                )

        return factory.create_response(wrapped())
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@dataclass(frozen=True)
class ServerSentEvent:
    """Data transfer object for a single Server-Sent Event.

    Serialisation / encoding is the responsibility of the web-layer
    implementation (e.g. ``quadkit-web``).

    Attributes:
        data: Event payload — any JSON-serialisable object or plain string.
        event: Optional event type name (sent as ``event:`` field).
        event_id: Optional event identifier (sent as ``id:`` field).
        retry: Optional reconnect interval in milliseconds.
    """

    data: Any
    event: str | None = field(default=None)
    event_id: str | None = field(default=None)
    retry: int | None = field(default=None)


@runtime_checkable
class SseResponseFactoryProtocol(Protocol):
    """Factory that wraps an async generator of ``ServerSentEvent`` objects
    into a framework HTTP response suitable for streaming SSE.

    Implementations are provided by ``quadkit-web`` and registered in the
    DI container during ``WebProvider.boot()``.

    Example::

        factory = await container.resolve(SseResponseFactoryProtocol)
        response = factory.create_response(my_event_generator())
    """

    def create_response(
        self,
        generator: AsyncGenerator[ServerSentEvent, None],
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Wrap *generator* into a streaming SSE HTTP response.

        Args:
            generator: Async generator yielding ``ServerSentEvent`` objects.
            status_code: HTTP status code for the response (default 200).
            headers: Optional additional response headers.

        Returns:
            A framework-specific streaming response object.
        """
        ...


@runtime_checkable
class ReactiveSseBridgeProtocol(Protocol):
    """Bridge a reactive event stream into a streaming SSE HTTP response.

    Implementations are provided by ``quadkit-web``
    (``quadkit.web.transport.reactive.sse_from_stream``) and registered in
    the DI container during ``WebProvider.register()``.  Consumers such as
    ``quadkit-admin`` resolve this protocol instead of importing the
    bridge from ``quadkit-web`` directly.

    Example::

        bridge = await container.resolve(ReactiveSseBridgeProtocol)
        response = bridge(
            event_stream,
            serializer=lambda event: dumps_str(event.to_dict()),
        )
    """

    def __call__(
        self,
        stream: Any,
        serializer: Callable[[Any], str] | None = None,
        event_name: str | None = None,
        keepalive: float | None = 15.0,
    ) -> Any:
        """Expose *stream* as an SSE HTTP response.

        Args:
            stream: A reactive event stream (``quadkit.reactive``).
            serializer: Optional item → frame-string serializer; defaults
                to ``str(item)``.
            event_name: Optional SSE ``event:`` field value.
            keepalive: Emit keepalive comments after this many seconds of
                silence; ``None`` disables.

        Returns:
            A streaming SSE HTTP response.
        """
        ...


__all__ = [
    "ReactiveSseBridgeProtocol",
    "ServerSentEvent",
    "SseResponseFactoryProtocol",
]
