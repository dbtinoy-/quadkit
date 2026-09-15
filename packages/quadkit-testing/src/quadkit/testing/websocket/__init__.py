"""WebSocket testing utilities.

Provides in-memory WebSocket test clients for testing WebSocket
handlers without requiring a real server connection.
"""

from __future__ import annotations

from quadkit.testing.websocket.client import WebSocketTestClient

__all__ = ["WebSocketTestClient"]
