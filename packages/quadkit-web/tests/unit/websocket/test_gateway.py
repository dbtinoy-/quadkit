"""Unit tests for WebSocketGateway and related decorators."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.web.websocket.gateway import (
    WebSocketGateway,
    on_connect,
    on_disconnect,
    on_error,
    subscribe_message,
    websocket_gateway,
)


def make_mock_ws() -> MagicMock:
    """Helper: create a mock WebSocket."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestSubscribeMessageDispatch:
    """Tests for @subscribe_message message dispatch."""

    @pytest.mark.asyncio
    async def test_dispatches_to_correct_handler(self):
        """@subscribe_message routes message by type field."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.received = None

            @subscribe_message("chat.send")
            async def handle_send(self, ws, payload):
                self.received = payload

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_message(ws, {"type": "chat.send", "text": "hello"})

        assert gw.received == {"text": "hello"}

    @pytest.mark.asyncio
    async def test_dispatches_to_second_event_type(self):
        """Separate handlers for different event types both work."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.events: list[str] = []

            @subscribe_message("ping")
            async def handle_ping(self, ws, payload):
                self.events.append("ping")

            @subscribe_message("pong")
            async def handle_pong(self, ws, payload):
                self.events.append("pong")

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_message(ws, {"type": "ping"})
        await gw.on_message(ws, {"type": "pong"})

        assert gw.events == ["ping", "pong"]

    @pytest.mark.asyncio
    async def test_strips_type_from_payload(self):
        """The 'type' key is removed from payload before passing."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.payload = None

            @subscribe_message("room.join")
            async def handle_join(self, ws, payload):
                self.payload = payload

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_message(ws, {"type": "room.join", "room": "general", "user": "alice"})

        assert "type" not in gw.payload
        assert gw.payload == {"room": "general", "user": "alice"}

    @pytest.mark.asyncio
    async def test_unhandled_message_calls_on_unhandled(self):
        """Unknown type triggers on_unhandled_message."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.unhandled = None

            async def on_unhandled_message(self, ws, message):
                self.unhandled = message

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_message(ws, {"type": "unknown.event"})

        assert gw.unhandled is not None
        assert gw.unhandled["type"] == "unknown.event"

    @pytest.mark.asyncio
    async def test_message_without_type_goes_to_unhandled(self):
        """Messages with no 'type' field go to on_unhandled_message."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.unhandled = None

            async def on_unhandled_message(self, ws, message):
                self.unhandled = message

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_message(ws, {"data": "raw"})

        assert gw.unhandled == {"data": "raw"}


class TestLifecycleDecorators:
    """Tests for @on_connect, @on_disconnect, @on_error decorators."""

    @pytest.mark.asyncio
    async def test_on_connect_decorator_is_called(self):
        """@on_connect routes the connect lifecycle."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.connected = False

            @on_connect
            async def handle_connect(self, ws):
                self.connected = True
                await ws.accept()

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_connect(ws)

        assert gw.connected is True
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_default_on_connect_accepts(self):
        """Default on_connect (no decorator) calls websocket.accept()."""

        class MyGateway(WebSocketGateway):
            pass

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_connect(ws)

        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_on_disconnect_decorator_is_called(self):
        """@on_disconnect routes the disconnect lifecycle."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.disconnected = False

            @on_disconnect
            async def handle_disconnect(self, ws):
                self.disconnected = True

        gw = MyGateway()
        ws = make_mock_ws()

        await gw.on_disconnect(ws)

        assert gw.disconnected is True

    @pytest.mark.asyncio
    async def test_on_error_decorator_is_called(self):
        """@on_error routes the error lifecycle."""

        class MyGateway(WebSocketGateway):
            def __init__(self):
                super().__init__()
                self.error = None

            @on_error
            async def handle_error(self, ws, error):
                self.error = error

        gw = MyGateway()
        ws = make_mock_ws()
        exc = ValueError("oops")

        await gw.on_error(ws, exc)

        assert gw.error is exc


class TestWebsocketGatewayDecorator:
    """Tests for the @websocket_gateway class decorator."""

    def test_sets_ws_path(self):
        """@websocket_gateway stores path metadata."""

        @websocket_gateway("/ws/test")
        class TestGateway(WebSocketGateway):
            pass

        assert TestGateway._ws_path == "/ws/test"
        assert TestGateway._is_websocket_handler is True
        assert TestGateway._is_websocket_gateway is True

    def test_sets_ping_interval(self):
        """@websocket_gateway passes config overrides to class."""

        @websocket_gateway("/ws/test", ping_interval=60)
        class TestGateway(WebSocketGateway):
            pass

        assert TestGateway.ping_interval == 60
