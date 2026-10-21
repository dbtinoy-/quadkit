"""Unit tests for the outbound WebSocket transport."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from quadkit.http.websocket import WebSocketClient, WebSocketMessage


def _frame(msg_type: aiohttp.WSMsgType, data: Any = None) -> SimpleNamespace:
    """A stand-in for aiohttp's WSMessage, which is a namedtuple we only read."""
    return SimpleNamespace(type=msg_type, data=data)


def _connected_client(socket: AsyncMock | None = None) -> WebSocketClient:
    """A client whose socket is already attached, bypassing __aenter__."""
    client = WebSocketClient("ws://example.test/socket")
    client._socket = socket if socket is not None else AsyncMock(closed=False)
    return client


class TestWebSocketMessage:
    """The normalized message value object."""

    def test_defaults(self) -> None:
        message = WebSocketMessage("text")
        assert message.type == "text"
        assert message.data is None

    def test_is_frozen(self) -> None:
        message = WebSocketMessage("text", "payload")
        with pytest.raises(FrozenInstanceError):
            message.type = "bytes"  # type: ignore[misc]


class TestConstruction:
    """Scheme validation and stored configuration."""

    @pytest.mark.parametrize("url", ["ws://example.test/s", "wss://example.test/s"])
    def test_accepts_websocket_schemes(self, url: str) -> None:
        client = WebSocketClient(url)
        assert client.url == url

    @pytest.mark.parametrize(
        "url", ["http://example.test", "https://example.test", "example.test"]
    )
    def test_rejects_non_websocket_schemes(self, url: str) -> None:
        with pytest.raises(ValueError, match="must start with ws:// or wss://"):
            WebSocketClient(url)

    def test_defaults(self) -> None:
        client = WebSocketClient("ws://example.test/s")
        assert client.headers == {}
        assert client.connect_timeout == 30.0
        assert client.heartbeat == 30.0
        assert client._session is None
        assert client._socket is None

    def test_overrides(self) -> None:
        client = WebSocketClient(
            "wss://example.test/s",
            headers={"Authorization": "Bearer t"},
            connect_timeout=5.0,
            heartbeat=None,
        )
        assert client.headers == {"Authorization": "Bearer t"}
        assert client.connect_timeout == 5.0
        assert client.heartbeat is None


class TestClosedProperty:
    """`closed` reports the upstream socket, not the wrapper."""

    def test_true_before_connect(self) -> None:
        assert WebSocketClient("ws://example.test/s").closed is True

    def test_false_while_socket_open(self) -> None:
        assert _connected_client(AsyncMock(closed=False)).closed is False

    def test_true_once_socket_closed(self) -> None:
        assert _connected_client(AsyncMock(closed=True)).closed is True


class TestSendRequiresConnection:
    """Every send fails fast rather than silently dropping the frame."""

    async def test_send_json(self) -> None:
        with pytest.raises(RuntimeError, match="not connected"):
            await WebSocketClient("ws://example.test/s").send_json({"a": 1})

    async def test_send_text(self) -> None:
        with pytest.raises(RuntimeError, match="not connected"):
            await WebSocketClient("ws://example.test/s").send_text("hi")

    async def test_send_bytes(self) -> None:
        with pytest.raises(RuntimeError, match="not connected"):
            await WebSocketClient("ws://example.test/s").send_bytes(b"\x00")

    async def test_receive(self) -> None:
        with pytest.raises(RuntimeError, match="not connected"):
            await WebSocketClient("ws://example.test/s").receive()


class TestSendDelegation:
    """Connected sends reach the matching aiohttp call."""

    async def test_send_json(self) -> None:
        socket = AsyncMock(closed=False)
        await _connected_client(socket).send_json({"a": 1})
        socket.send_json.assert_awaited_once_with({"a": 1})

    async def test_send_text(self) -> None:
        socket = AsyncMock(closed=False)
        await _connected_client(socket).send_text("hi")
        socket.send_str.assert_awaited_once_with("hi")

    async def test_send_bytes(self) -> None:
        socket = AsyncMock(closed=False)
        await _connected_client(socket).send_bytes(b"\x01")
        socket.send_bytes.assert_awaited_once_with(b"\x01")


class TestReceiveNormalization:
    """Upstream frame types map onto the transport's own vocabulary."""

    async def test_text(self) -> None:
        socket = AsyncMock(closed=False)
        socket.receive.return_value = _frame(aiohttp.WSMsgType.TEXT, "hello")
        assert await _connected_client(socket).receive() == WebSocketMessage(
            "text", "hello"
        )

    async def test_binary(self) -> None:
        socket = AsyncMock(closed=False)
        socket.receive.return_value = _frame(aiohttp.WSMsgType.BINARY, b"\x01\x02")
        assert await _connected_client(socket).receive() == WebSocketMessage(
            "bytes", b"\x01\x02"
        )

    @pytest.mark.parametrize(
        "msg_type", [aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED]
    )
    async def test_close_frames(self, msg_type: aiohttp.WSMsgType) -> None:
        socket = AsyncMock(closed=False)
        socket.receive.return_value = _frame(msg_type, None)
        assert await _connected_client(socket).receive() == WebSocketMessage(
            "close", None
        )

    async def test_error_stringifies_the_exception(self) -> None:
        socket = AsyncMock(closed=False)
        socket.receive.return_value = _frame(
            aiohttp.WSMsgType.ERROR, ValueError("boom")
        )
        message = await _connected_client(socket).receive()
        assert message.type == "error"
        assert message.data == "boom"

    async def test_control_frames_are_exposed_lowercased(self) -> None:
        """Ping/pong are autoping'd, but callers can still see them."""
        socket = AsyncMock(closed=False)
        socket.receive.return_value = _frame(aiohttp.WSMsgType.PING, b"")
        message = await _connected_client(socket).receive()
        assert message.type == str(aiohttp.WSMsgType.PING).lower()
        assert message.data == b""


class TestConnectionLifecycle:
    """__aenter__ owns the session, including when the handshake fails."""

    async def test_aenter_connects_and_returns_self(self) -> None:
        socket = AsyncMock(closed=False)
        session = MagicMock()
        session.ws_connect = AsyncMock(return_value=socket)
        session.close = AsyncMock()

        with patch(
            "quadkit.http.websocket.aiohttp.ClientSession", return_value=session
        ):
            client = WebSocketClient(
                "wss://example.test/s", headers={"X": "1"}, heartbeat=7.0
            )
            entered = await client.__aenter__()

        assert entered is client
        assert client._session is session
        assert client._socket is socket
        session.ws_connect.assert_awaited_once_with(
            "wss://example.test/s",
            headers={"X": "1"},
            heartbeat=7.0,
            autoping=True,
        )
        session.close.assert_not_awaited()

    async def test_aenter_closes_the_session_when_the_handshake_fails(self) -> None:
        """A failed connect must not leak the ClientSession it just opened."""
        session = MagicMock()
        session.ws_connect = AsyncMock(side_effect=OSError("refused"))
        session.close = AsyncMock()

        with patch(
            "quadkit.http.websocket.aiohttp.ClientSession", return_value=session
        ):
            client = WebSocketClient("ws://example.test/s")
            with pytest.raises(OSError, match="refused"):
                await client.__aenter__()

        session.close.assert_awaited_once()
        assert client._session is None
        assert client.closed is True

    async def test_aexit_closes(self) -> None:
        client = _connected_client(AsyncMock(closed=False))
        client._session = MagicMock(close=AsyncMock())
        await client.__aexit__(None, None, None)
        assert client._socket is None
        assert client._session is None


class TestClose:
    """close() is safe to call on an already-torn-down client."""

    async def test_closes_open_socket_and_session(self) -> None:
        socket = AsyncMock(closed=False)
        session = MagicMock(close=AsyncMock())
        client = _connected_client(socket)
        client._session = session

        await client.close()

        socket.close.assert_awaited_once()
        session.close.assert_awaited_once()
        assert client._socket is None
        assert client._session is None

    async def test_skips_an_already_closed_socket(self) -> None:
        socket = AsyncMock(closed=True)
        client = _connected_client(socket)
        await client.close()
        socket.close.assert_not_awaited()

    async def test_idempotent_on_a_fresh_client(self) -> None:
        client = WebSocketClient("ws://example.test/s")
        await client.close()
        await client.close()
        assert client.closed is True
