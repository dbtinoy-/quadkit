"""Tests for WebSocket room manager."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.web.websocket.rooms import RoomManager, get_room_manager, set_room_manager


def _mock_ws(user_id: str | None = None):
    """Create a mock WebSocket with optional user_id state."""
    ws = MagicMock()
    ws.send_text = AsyncMock()
    state = MagicMock()
    state.user_id = user_id
    ws.state = state
    return ws


class TestRoomManager:
    @pytest.mark.asyncio
    async def test_join_adds_to_room(self) -> None:
        manager = RoomManager()
        ws = _mock_ws()
        await manager.join("chat", ws)
        assert ws in manager.members("chat")

    @pytest.mark.asyncio
    async def test_join_creates_room_if_missing(self) -> None:
        manager = RoomManager()
        ws = _mock_ws()
        await manager.join("new-room", ws)
        assert manager.room_count("new-room") == 1

    @pytest.mark.asyncio
    async def test_leave_removes_from_room(self) -> None:
        manager = RoomManager()
        ws = _mock_ws()
        await manager.join("chat", ws)
        await manager.leave("chat", ws)
        assert ws not in manager.members("chat")

    @pytest.mark.asyncio
    async def test_leave_deletes_empty_room(self) -> None:
        manager = RoomManager()
        ws = _mock_ws()
        await manager.join("chat", ws)
        await manager.leave("chat", ws)
        assert manager.room_count("chat") == 0

    @pytest.mark.asyncio
    async def test_leave_all_removes_from_all_rooms(self) -> None:
        manager = RoomManager()
        ws = _mock_ws()
        await manager.join("room-a", ws)
        await manager.join("room-b", ws)
        await manager.leave_all(ws)
        assert ws not in manager.members("room-a")
        assert ws not in manager.members("room-b")

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_members(self) -> None:
        manager = RoomManager()
        ws1 = _mock_ws()
        ws2 = _mock_ws()
        await manager.join("chat", ws1)
        await manager.join("chat", ws2)
        await manager.broadcast("chat", "hello")
        ws1.send_text.assert_awaited_once_with("hello")
        ws2.send_text.assert_awaited_once_with("hello")

    @pytest.mark.asyncio
    async def test_broadcast_excludes_sender(self) -> None:
        manager = RoomManager()
        sender = _mock_ws()
        receiver = _mock_ws()
        await manager.join("chat", sender)
        await manager.join("chat", receiver)
        await manager.broadcast("chat", "hi", exclude=sender)
        sender.send_text.assert_not_awaited()
        receiver.send_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_room_is_noop(self) -> None:
        manager = RoomManager()
        # Should not raise
        await manager.broadcast("ghost-room", "msg")

    @pytest.mark.asyncio

    async def test_send_to_specific_user(self) -> None:
        manager = RoomManager()
        target = _mock_ws(user_id="u1")
        other = _mock_ws(user_id="u2")
        await manager.join("chat", target)
        await manager.join("chat", other)
        result = await manager.send_to("chat", "u1", "private msg")
        assert result.is_ok()
        target.send_text.assert_awaited_once_with("private msg")
        other.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_room_is_noop(self) -> None:
        manager = RoomManager()
        result = await manager.send_to("ghost", "u1", "msg")
        assert result.is_err()
        assert result.unwrap_err().reason == "room not found"

    def test_members_returns_copy(self) -> None:
        manager = RoomManager()
        members1 = manager.members("room")
        members2 = manager.members("room")
        assert members1 is not members2

    @pytest.mark.asyncio
    async def test_rooms_for_returns_rooms(self) -> None:
        manager = RoomManager()
        ws = _mock_ws()
        await manager.join("r1", ws)
        await manager.join("r2", ws)
        rooms = manager.rooms_for(ws)
        assert "r1" in rooms
        assert "r2" in rooms

    def test_room_count_empty(self) -> None:
        manager = RoomManager()
        assert manager.room_count("empty") == 0


class TestGetSetRoomManager:
    def test_set_and_get_room_manager(self) -> None:
        import quadkit.web.websocket.rooms as rooms_mod
        original = rooms_mod._room_manager
        try:
            custom = RoomManager()
            set_room_manager(custom)
            with patch("quadkit.di.resolution.context.get_resolver", return_value=None):
                retrieved = get_room_manager()
            assert retrieved is custom
        finally:
            rooms_mod._room_manager = original

    def test_get_room_manager_creates_default_if_none(self) -> None:
        import quadkit.web.websocket.rooms as rooms_mod
        original = rooms_mod._room_manager
        try:
            rooms_mod._room_manager = None
            with patch("quadkit.di.resolution.context.get_resolver", return_value=None):
                manager = get_room_manager()
            assert isinstance(manager, RoomManager)
        finally:
            rooms_mod._room_manager = original
