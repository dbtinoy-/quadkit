"""Convention followed: **Service pattern** — domain state and rules behind
a plain class, injected through the provider; no HTTP knowledge here.

Room membership for the WebSocket Echo demo.
"""

from __future__ import annotations


class RoomFullError(Exception):
    """Raised when joining a room whose configured member cap is reached."""


class ConnectionRegistry:
    """Counts live connections per room; shared by handler and controller."""

    def __init__(self, max_room_members: int = 0) -> None:
        self.max_room_members = max_room_members
        self.counts: dict[str, int] = {}

    def join(self, room: str) -> int:
        """Join ``room``; return the new member's join order (1-based).

        Raises:
            RoomFullError: when the configured cap (if any) is reached.
        """
        current = self.counts.get(room, 0)
        if self.max_room_members and current >= self.max_room_members:
            raise RoomFullError(room)
        self.counts[room] = current + 1
        return current + 1

    def leave(self, room: str) -> int:
        """Leave ``room``; return the remaining member count (never < 0)."""
        self.counts[room] = max(0, self.counts.get(room, 0) - 1)
        return self.counts[room]


__all__ = ["ConnectionRegistry", "RoomFullError"]
