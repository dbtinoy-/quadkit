"""ASGI WebSocket endpoint for streaming events to connected clients.

Clients connect via WebSocket and receive a JSON-serialised stream of events
dispatched through a :class:`~quadkit.events.streaming.dispatcher.StreamDispatcher`.

Protocol
--------
Once the WebSocket handshake is complete, the server begins forwarding every
event published to the dispatcher as a UTF-8 JSON frame.  Each frame has the
shape::

    {
        "event_type": "<str>",
        "event_id":   "<UUID>",
        "occurred_at": "<ISO-8601 datetime>",
        "data":        { ... }   // event-specific payload
    }

The client may send a ``{"action": "ping"}`` frame at any time; the server
responds with ``{"action": "pong"}``.  Any other client message is silently
ignored.

Clients disconnect by closing the WebSocket normally; the server also closes
the connection gracefully when the ASGI lifespan ends.

Example
-------
Mount the endpoint under any ASGI router; pass an ``authorize`` callback
to control which connections are accepted::

    from quadkit.events.streaming import StreamDispatcher
    from quadkit.events.streaming.websocket import EventWebSocketEndpoint

    dispatcher = StreamDispatcher()

    def authorize(scope: dict) -> bool:
        # Reject connections that do not present a valid token.
        headers = dict(scope.get("headers") or [])
        return headers.get(b"authorization") == b"Bearer secret"

    ws_app = EventWebSocketEndpoint(dispatcher, authorize=authorize)

    # With a bare ASGI server router:
    # app = routes.Router(routes=[Route("/ws/events", ws_app)])

Warning
-------
By default (``authorize=None``) **every** connection is accepted and
receives a real-time stream of **all** events published to the
dispatcher.  Mounting this endpoint without an ``authorize`` callback
exposes an unauthenticated firehose of every dispatched event — which
may include business-sensitive or PII-bearing payloads.  Always pass an
``authorize`` callback in production; the callback receives the ASGI
``scope`` and may be synchronous or asynchronous.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import inspect
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from quadkit.events.streaming.dispatcher import StreamDispatcher

logger = get_logger(__name__)

# ASGI type aliases (stdlib-only, no starlette dependency)
_Scope = dict[str, Any]
_Receive = Callable[[], Any]
_Send = Callable[[dict[str, Any]], Any]


def _event_to_dict(event: Any) -> dict[str, Any]:
    """Serialise an event to a JSON-compatible dictionary.

    Args:
        event: A domain event instance.

    Returns:
        Dictionary representation safe for ``json.dumps``.
    """
    payload: dict[str, Any] = {}

    # Prefer ``__dict__`` for dataclass-based events
    raw = getattr(event, "__dict__", None)
    if raw is None:
        raw = {}

    for key, val in raw.items():
        if key.startswith("_"):
            continue
        try:
            payload[key] = (
                str(val)
                if not isinstance(val, (str, int, float, bool, type(None)))
                else val
            )
        except Exception as e:  # noqa: BLE001 — best-effort serialisation; val type is unknown
            logger.debug("event_field_serialisation_failed", field=key, error=str(e))
            payload[key] = repr(val)

    return {
        "event_type": getattr(event, "event_type", type(event).__name__),
        "event_id": str(getattr(event, "event_id", uuid4())),
        "occurred_at": str(getattr(event, "occurred_at", "")),
        "data": payload,
    }


class EventWebSocketEndpoint:
    """ASGI application that streams events over WebSocket.

    Subscribes to a :class:`~quadkit.events.streaming.dispatcher.StreamDispatcher`
    and forwards every published event to connected clients as a JSON frame.

    Each connected client gets its own subscription; subscriptions are cleaned up
    automatically when the client disconnects or the connection is lost.

    Args:
        dispatcher: The stream dispatcher to receive events from.
        ping_interval: Seconds between server-originated keepalive ping frames.
            Set to ``0`` to disable keepalives.
        authorize: Optional callback that decides whether a connection may
            proceed. See ``__init__`` for the full contract.

    Example:
        ```python
        dispatcher = StreamDispatcher()
        ws_app = EventWebSocketEndpoint(dispatcher)
        await ws_app(scope, receive, send)
        ```
    """

    def __init__(
        self,
        dispatcher: StreamDispatcher,
        ping_interval: float = 30.0,
        authorize: (
            Callable[[_Scope], bool] | Callable[[_Scope], Awaitable[bool]] | None
        ) = None,
    ) -> None:
        """Initialise the WebSocket endpoint.

        Args:
            dispatcher: Dispatcher whose events will be forwarded to clients.
            ping_interval: Server keepalive interval in seconds (0 to disable).
            authorize: Optional callback deciding whether a connection may
                proceed. Receives the ASGI connection ``scope``; return a
                truthy value to accept the connection or a falsy value to
                reject it with close code 4401 before the handshake is
                accepted. May be synchronous or asynchronous. When ``None``
                (default), every connection is accepted — see the module
                docstring warning.
        """
        self._dispatcher = dispatcher
        self._ping_interval = ping_interval
        self._authorize = authorize

    async def __call__(
        self,
        scope: _Scope,
        receive: _Receive,
        send: _Send,
    ) -> None:
        """ASGI entry point.

        Args:
            scope: ASGI connection scope.  Only ``websocket`` type is handled;
                other types receive a ``400`` text response.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "websocket":
            await send(
                {
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [],
                }
            )
            await send({"type": "http.response.body", "body": b"WebSocket required"})
            return

        await self._handle_websocket(scope, receive, send)

    async def _handle_websocket(
        self,
        scope: _Scope,
        receive: _Receive,
        send: _Send,
    ) -> None:
        """Manage a single WebSocket connection lifecycle.

        Args:
            scope: ASGI connection scope.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        # Accept the WebSocket handshake
        connect_msg = await receive()
        if connect_msg.get("type") != "websocket.connect":
            return

        if self._authorize is not None:
            decision = self._authorize(scope)
            if inspect.isawaitable(decision):
                decision = await decision
            if not decision:
                await send({"type": "websocket.close", "code": 4401})
                logger.warning("ws_client_unauthorized", client=scope.get("client"))
                return

        await send({"type": "websocket.accept"})
        logger.info("ws_client_connected", client=scope.get("client"))

        queue: asyncio.Queue[Any] = asyncio.Queue()

        def _enqueue(event: Any) -> None:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "ws_queue_full_dropping_event",
                    event_type=getattr(event, "event_type", type(event).__name__),
                )

        subscription_id = self._dispatcher.subscribe_all(_enqueue)

        try:
            client_task = asyncio.create_task(self._receive_loop(receive, send))
            if not hasattr(self, "_active_tasks"):
                self._active_tasks: set[asyncio.Task[Any]] = set()
            self._active_tasks.add(client_task)
            client_task.add_done_callback(self._active_tasks.discard)

            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=self._ping_interval or None
                    )
                    raw = dumps(_event_to_dict(event))
                    frame = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                    await send({"type": "websocket.send", "text": frame})
                except TimeoutError:
                    # Send keepalive ping
                    if self._ping_interval > 0:
                        try:
                            await send(
                                {"type": "websocket.send", "text": '{"action":"ping"}'}
                            )
                        except Exception as e:  # noqa: BLE001
                            logger.warning("ws_keepalive_send_failed", error=str(e))
                            break
                except asyncio.CancelledError:
                    break

                if client_task.done():
                    break
        finally:
            try:
                self._dispatcher.unsubscribe(subscription_id)
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "ws_unsubscribe_failed",
                    subscription_id=subscription_id,
                    error=str(e),
                )
            logger.info("ws_client_disconnected", client=scope.get("client"))
            try:
                await send({"type": "websocket.close", "code": 1000})
            except Exception as e:  # noqa: BLE001
                logger.debug("ws_close_send_failed", error=str(e))

    async def _receive_loop(
        self,
        receive: _Receive,
        send: _Send,
    ) -> None:
        """Process incoming client messages.

        Handles ``ping`` frames by responding with ``pong``.  Exits when the
        client sends a ``websocket.disconnect`` message.

        Args:
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        while True:
            msg = await receive()
            msg_type = msg.get("type")

            if msg_type == "websocket.disconnect":
                return

            if msg_type == "websocket.receive":
                text = msg.get("text") or (msg.get("bytes") or b"").decode(
                    "utf-8", errors="replace"
                )
                try:
                    data = loads(
                        text.encode("utf-8") if isinstance(text, str) else text
                    )
                    if data.get("action") == "ping":
                        await send(
                            {"type": "websocket.send", "text": '{"action":"pong"}'}
                        )
                except (ValueError, TypeError):
                    pass
