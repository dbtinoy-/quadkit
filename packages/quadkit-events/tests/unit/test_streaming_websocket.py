"""Unit tests for EventWebSocketEndpoint connection authorization."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.streaming import EventWebSocketEndpoint, StreamDispatcher


class _TestEvent(Event):
    """Test event."""

    value: str = "test"


def _ws_scope() -> dict[str, Any]:
    """Build a minimal ASGI websocket scope."""
    return {
        "type": "websocket",
        "headers": [(b"authorization", b"Bearer token-123")],
        "client": ("127.0.0.1", 45678),
        "query_string": b"",
        "path": "/ws/events",
    }


class _FakeSend:
    """ASGI send callable that records every message sent by the endpoint."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []
        self.accepted = asyncio.Event()
        self.frame_sent = asyncio.Event()

    async def __call__(self, message: dict[str, Any]) -> None:
        self.messages.append(message)
        if message.get("type") == "websocket.accept":
            self.accepted.set()
        elif message.get("type") == "websocket.send":
            self.frame_sent.set()


def _fake_receive(
    *messages: dict[str, Any],
) -> Callable[[], Awaitable[dict[str, Any]]]:
    """Build an ASGI receive callable yielding the given messages in order.

    When exhausted it loops with an empty message; the tests cancel the
    connection task before that matters for accept-path assertions.
    """

    queue = list(messages)

    async def _receive() -> dict[str, Any]:
        if queue:
            return queue.pop(0)
        await asyncio.sleep(0.05)
        return {}

    return _receive


async def _wait_for_subscriber(dispatcher: StreamDispatcher) -> None:
    """Wait until the dispatcher has one active subscriber (bounded poll)."""
    for _ in range(100):
        if dispatcher.stats.active_subscribers == 1:
            return
        await asyncio.sleep(0.01)


async def _cancel_connection(
    endpoint: EventWebSocketEndpoint, ws_task: asyncio.Task[Any]
) -> None:
    """Cancel a live connection task and clean up any leftover receive loop.

    The endpoint's streaming loop only exits via cancellation when no
    further events are published; absorb both normal and cancelled
    completion and cancel the per-connection ``_receive_loop`` child task.
    """
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass
    for task in list(endpoint._active_tasks):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _async_deny(scope: dict[str, Any]) -> bool:
    """Async authorize callback that rejects the connection."""
    return False


async def _async_allow(scope: dict[str, Any]) -> bool:
    """Async authorize callback that admits the connection."""
    return True


class TestWebSocketEndpointAuthorization:
    """Tests for the optional ``authorize`` callback."""

    @pytest.mark.asyncio
    async def test_default_no_authorize_accepts_and_streams_events(self) -> None:
        """With no authorize callback the connection is accepted unchanged."""
        dispatcher = StreamDispatcher()
        endpoint = EventWebSocketEndpoint(dispatcher, ping_interval=0)
        send = _FakeSend()
        receive = _fake_receive(
            {"type": "websocket.connect"}, {"type": "websocket.disconnect"}
        )

        ws_task = asyncio.create_task(endpoint(_ws_scope(), receive, send))
        await asyncio.wait_for(send.accepted.wait(), timeout=5)
        await _wait_for_subscriber(dispatcher)
        await dispatcher.publish(_TestEvent(aggregate_id=uuid4(), value="ok"))
        await asyncio.wait_for(send.frame_sent.wait(), timeout=5)
        await _cancel_connection(endpoint, ws_task)

        assert [m["type"] for m in send.messages] == [
            "websocket.accept",
            "websocket.send",
            "websocket.close",
        ]
        frame = json.loads(send.messages[1]["text"])
        assert frame["event_type"] == "_TestEvent"
        assert frame["data"]["value"] == "ok"
        assert dispatcher.stats.active_subscribers == 0

    @pytest.mark.asyncio
    async def test_sync_authorize_false_rejects_before_accept(self) -> None:
        """A sync authorize callback returning falsy closes without accepting."""
        dispatcher = StreamDispatcher()
        endpoint = EventWebSocketEndpoint(
            dispatcher, ping_interval=0, authorize=lambda scope: False
        )
        send = _FakeSend()
        receive = _fake_receive({"type": "websocket.connect"})

        await endpoint(_ws_scope(), receive, send)

        assert [m["type"] for m in send.messages] == ["websocket.close"]
        assert send.messages[0]["code"] == 4401
        assert not send.accepted.is_set()
        assert dispatcher.stats.active_subscribers == 0

    @pytest.mark.asyncio
    async def test_sync_authorize_true_accepts_and_receives_scope(self) -> None:
        """A sync authorize callback returning truthy accepts; scope is passed."""
        dispatcher = StreamDispatcher()
        captured: list[dict[str, Any]] = []

        def _authorize(scope: dict[str, Any]) -> bool:
            captured.append(scope)
            return scope["headers"][0][0] == b"authorization"

        endpoint = EventWebSocketEndpoint(
            dispatcher, ping_interval=0, authorize=_authorize
        )
        send = _FakeSend()
        receive = _fake_receive(
            {"type": "websocket.connect"}, {"type": "websocket.disconnect"}
        )
        scope = _ws_scope()

        ws_task = asyncio.create_task(endpoint(scope, receive, send))
        await asyncio.wait_for(send.accepted.wait(), timeout=5)
        await _wait_for_subscriber(dispatcher)
        await dispatcher.publish(_TestEvent(aggregate_id=uuid4(), value="ok"))
        await asyncio.wait_for(send.frame_sent.wait(), timeout=5)
        await _cancel_connection(endpoint, ws_task)

        assert len(captured) == 1
        assert captured[0] is scope
        assert [m["type"] for m in send.messages] == [
            "websocket.accept",
            "websocket.send",
            "websocket.close",
        ]
        assert dispatcher.stats.active_subscribers == 0

    @pytest.mark.asyncio
    async def test_async_authorize_false_rejects_before_accept(self) -> None:
        """An async authorize callback returning falsy closes without accepting."""
        dispatcher = StreamDispatcher()
        endpoint = EventWebSocketEndpoint(
            dispatcher, ping_interval=0, authorize=_async_deny
        )
        send = _FakeSend()
        receive = _fake_receive({"type": "websocket.connect"})

        await endpoint(_ws_scope(), receive, send)

        assert [m["type"] for m in send.messages] == ["websocket.close"]
        assert send.messages[0]["code"] == 4401
        assert not send.accepted.is_set()
        assert dispatcher.stats.active_subscribers == 0

    @pytest.mark.asyncio
    async def test_async_authorize_true_accepts_and_streams_events(self) -> None:
        """An async authorize callback returning truthy accepts the connection."""
        dispatcher = StreamDispatcher()
        endpoint = EventWebSocketEndpoint(
            dispatcher, ping_interval=0, authorize=_async_allow
        )
        send = _FakeSend()
        receive = _fake_receive(
            {"type": "websocket.connect"}, {"type": "websocket.disconnect"}
        )

        ws_task = asyncio.create_task(endpoint(_ws_scope(), receive, send))
        await asyncio.wait_for(send.accepted.wait(), timeout=5)
        await _wait_for_subscriber(dispatcher)
        await dispatcher.publish(_TestEvent(aggregate_id=uuid4(), value="ok"))
        await asyncio.wait_for(send.frame_sent.wait(), timeout=5)
        await _cancel_connection(endpoint, ws_task)

        assert [m["type"] for m in send.messages] == [
            "websocket.accept",
            "websocket.send",
            "websocket.close",
        ]
        frame = json.loads(send.messages[1]["text"])
        assert frame["event_type"] == "_TestEvent"
        assert dispatcher.stats.active_subscribers == 0
