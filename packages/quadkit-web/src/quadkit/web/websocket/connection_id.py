"""WebSocket connection ID management.

Provides stable, unique identifiers for WebSocket connections using UUID
instead of memory addresses. Prevents state leakage when Python reuses
memory addresses after garbage collection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid
import weakref

from quadkit.contracts.core.identity import IdGeneratorProtocol

if TYPE_CHECKING:
    from starlette.websockets import WebSocket


class ConnectionIDManager:
    """Manages stable UUID-based connection IDs for WebSocket instances.

    Each WebSocket is assigned a unique UUID when first registered.
    The mapping uses a WeakKeyDictionary so the UUID is automatically
    cleaned up when the WebSocket is garbage collected.
    """

    def __init__(self, id_generator: IdGeneratorProtocol | None = None) -> None:
        """Initialize the connection ID manager.

        Args:
            id_generator: Optional ID generator (defaults to uuid.uuid4).
        """
        self._ids = id_generator
        self._ws_to_id: weakref.WeakKeyDictionary[WebSocket, str] = (
            weakref.WeakKeyDictionary()
        )

    def get_or_create(self, websocket: WebSocket) -> str:
        """Get or create a stable UUID for the WebSocket.

        Args:
            websocket: The WebSocket connection.

        Returns:
            A unique string identifier (UUID) for this connection.
        """
        if websocket not in self._ws_to_id:
            self._ws_to_id[websocket] = (
                self._ids.generate() if self._ids else str(uuid.uuid4())
            )
        return self._ws_to_id[websocket]

    def get(self, websocket: WebSocket) -> str | None:
        """Get the UUID for a WebSocket, or None if not registered.

        Args:
            websocket: The WebSocket connection.

        Returns:
            The UUID if registered, None otherwise.
        """
        return self._ws_to_id.get(websocket)


__all__ = ["ConnectionIDManager"]
