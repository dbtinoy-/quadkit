"""WebSocket room management for group messaging.

Provides RoomManager for join/leave/broadcast semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result
from quadkit.web.websocket.connection_id import ConnectionIDManager

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

logger = get_logger(__name__)


@dataclass(frozen=True)
class RoomError:
    """Error type for room operations."""

    reason: str


class RoomManager:
    """Manages WebSocket rooms with join/leave/broadcast semantics."""

    def __init__(
        self,
        connection_id_manager: ConnectionIDManager | None = None,
    ) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        # Track which rooms a user is in (by connection UUID)
        self._user_rooms: dict[str, set[str]] = {}
        self._connection_id_manager = (
            connection_id_manager
            if connection_id_manager is not None
            else ConnectionIDManager()
        )

    async def join(self, room: str, websocket: WebSocket) -> None:
        """Add a WebSocket to a room."""
        if room not in self._rooms:
            self._rooms[room] = set()
        self._rooms[room].add(websocket)

        # Track user's rooms
        ws_uuid = self._connection_id_manager.get_or_create(websocket)
        if ws_uuid not in self._user_rooms:
            self._user_rooms[ws_uuid] = set()
        self._user_rooms[ws_uuid].add(room)

    async def leave(self, room: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from a room."""
        if room in self._rooms:
            self._rooms[room].discard(websocket)
            if not self._rooms[room]:
                del self._rooms[room]

        # Update user's room tracking
        ws_uuid = self._connection_id_manager.get_or_create(websocket)
        if ws_uuid in self._user_rooms:
            self._user_rooms[ws_uuid].discard(room)

    async def leave_all(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from all rooms."""
        ws_uuid = self._connection_id_manager.get_or_create(websocket)
        if ws_uuid in self._user_rooms:
            rooms = list(self._user_rooms[ws_uuid])
            for room in rooms:
                await self.leave(room, websocket)

    async def broadcast(
        self,
        room: str,
        message: Any,
        exclude: WebSocket | None = None,
    ) -> None:
        """Broadcast a message to all WebSockets in a room."""
        if room not in self._rooms:
            return

        # Serialize message if needed
        if not isinstance(message, str):
            from quadkit import serialization as json

            message = json.dumps(message)

        # Send to all except excluded
        for ws in self._rooms[room]:
            if ws is exclude:
                continue
            try:
                await ws.send_text(message)
            except (OSError, RuntimeError):
                # Remove broken connections
                await self.leave(room, ws)

    async def send_to(
        self,
        room: str,
        user_id: str,
        message: Any,
    ) -> Result[None, RoomError]:
        """Send a message to a specific user in a room (by user_id).

        Note: This requires the WebSocket to have user_id stored in its state.
        """
        if room not in self._rooms:
            return Err(RoomError(reason="room not found"))

        # Serialize message if needed
        if not isinstance(message, str):
            from quadkit import serialization as json

            message = json.dumps(message)

        for ws in self._rooms[room]:
            if getattr(ws.state, "user_id", None) == user_id:
                try:
                    await ws.send_text(message)
                    return Ok(None)
                except (OSError, RuntimeError) as exc:
                    logger.debug("websocket_send_failed", error=str(exc))
                    return Err(RoomError(reason=f"websocket disconnected: {exc}"))

        return Err(RoomError(reason="user not in room"))

    def members(self, room: str) -> set[WebSocket]:
        """Get all WebSockets in a room."""
        return self._rooms.get(room, set()).copy()

    def rooms_for(self, websocket: WebSocket) -> set[str]:
        """Get all rooms a WebSocket is in."""
        ws_uuid = self._connection_id_manager.get_or_create(websocket)
        return self._user_rooms.get(ws_uuid, set()).copy()

    def room_count(self, room: str) -> int:
        """Get the number of members in a room."""
        return len(self._rooms.get(room, set()))


# Global room manager instance
_room_manager: RoomManager | None = None


def get_room_manager(context: Any | None = None) -> RoomManager:
    """Get the global RoomManager instance."""
    from quadkit.di.resolution.context import get_resolver

    resolver = get_resolver(context)
    if resolver:
        return cast("RoomManager", cast("Any", resolver).resolve_sync(RoomManager))

    global _room_manager
    if _room_manager is None:
        _room_manager = RoomManager()
    return _room_manager


def set_room_manager(manager: RoomManager) -> None:
    """Set a custom RoomManager instance."""
    global _room_manager
    _room_manager = manager
