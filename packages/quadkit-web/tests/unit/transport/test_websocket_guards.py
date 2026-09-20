"""Tests for transport/websocket_guards.py — execute_websocket_guards, GuardedWebSocket."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.web.security.guards import GuardRejection
from quadkit.web.transport.websocket_guards import (
    GuardedWebSocket,
    execute_websocket_guards,
)


def _mock_websocket() -> MagicMock:
    ws = MagicMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_bytes = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock(return_value="received_text")
    ws.receive_bytes = AsyncMock(return_value=b"received_bytes")
    ws.receive_json = AsyncMock(return_value={"key": "val"})
    ws.client_state = MagicMock()
    ws.application_state = MagicMock()
    return ws


def _allow_guard() -> MagicMock:
    guard = MagicMock()
    guard.can_activate = AsyncMock(return_value=True)
    return guard


def _deny_guard() -> MagicMock:
    guard = MagicMock()
    guard.can_activate = AsyncMock(return_value=False)
    return guard


class TestExecuteWebSocketGuards:
    @pytest.mark.asyncio
    async def test_empty_guards_returns_ok(self) -> None:
        ws = _mock_websocket()
        result = await execute_websocket_guards([], ws)
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_all_guards_pass_returns_ok(self) -> None:
        ws = _mock_websocket()
        result = await execute_websocket_guards([_allow_guard(), _allow_guard()], ws)
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_failing_guard_rejects_and_returns_err(self) -> None:
        ws = _mock_websocket()
        result = await execute_websocket_guards([_deny_guard()], ws)
        assert result.is_err()
        assert isinstance(result.unwrap_err(), GuardRejection)
        ws.close.assert_awaited_once_with(code=4003, reason="Forbidden")

    @pytest.mark.asyncio
    async def test_short_circuits_on_first_failure(self) -> None:
        ws = _mock_websocket()
        second_guard = _allow_guard()
        result = await execute_websocket_guards([_deny_guard(), second_guard], ws)
        assert result.is_err()
        second_guard.can_activate.assert_not_awaited()


class TestGuardedWebSocket:
    def test_init_stores_websocket_and_guards(self) -> None:
        ws = _mock_websocket()
        guard = _allow_guard()
        gws = GuardedWebSocket(ws, [guard])
        assert gws.websocket is ws
        assert guard in gws.guards
        assert gws._accepted is False

    def test_init_defaults_empty_guards(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        assert gws.guards == []

    @pytest.mark.asyncio
    async def test_accept_calls_websocket_accept_when_guards_pass(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws, [_allow_guard()])
        await gws.accept()
        ws.accept.assert_awaited_once_with(subprotocol=None)
        assert gws._accepted is True

    @pytest.mark.asyncio
    async def test_accept_with_subprotocol(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        await gws.accept(subprotocol="chat")
        ws.accept.assert_awaited_once_with(subprotocol="chat")

    @pytest.mark.asyncio
    async def test_accept_denied_guard_does_not_call_accept(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws, [_deny_guard()])
        await gws.accept()
        ws.accept.assert_not_awaited()
        assert gws._accepted is False

    @pytest.mark.asyncio
    async def test_accept_no_guards_skips_guard_check(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws, [])
        await gws.accept()
        ws.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_text(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        await gws.send_text("hello")
        ws.send_text.assert_awaited_once_with("hello")

    @pytest.mark.asyncio
    async def test_send_bytes(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        await gws.send_bytes(b"data")
        ws.send_bytes.assert_awaited_once_with(b"data")

    @pytest.mark.asyncio
    async def test_send_json(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        await gws.send_json({"k": "v"})
        ws.send_json.assert_awaited_once_with({"k": "v"})

    @pytest.mark.asyncio
    async def test_receive_text(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        result = await gws.receive_text()
        assert result == "received_text"

    @pytest.mark.asyncio
    async def test_receive_bytes(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        result = await gws.receive_bytes()
        assert result == b"received_bytes"

    @pytest.mark.asyncio
    async def test_receive_json(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        result = await gws.receive_json()
        assert result == {"key": "val"}

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        await gws.close(code=4000, reason="bye")
        ws.close.assert_awaited_once_with(code=4000, reason="bye")

    def test_client_state_proxies_to_websocket(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        assert gws.client_state is ws.client_state

    def test_application_state_proxies_to_websocket(self) -> None:
        ws = _mock_websocket()
        gws = GuardedWebSocket(ws)
        assert gws.application_state is ws.application_state
