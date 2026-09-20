"""Tests for the Quadkit WebSocket transport wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock

from quadkit.web.transport.websockets import WebSocket


def test_path_params_are_exposed_from_starlette_websocket() -> None:
    """Handlers can read route parameters through the framework wrapper."""
    starlette_websocket = MagicMock()
    starlette_websocket.path_params = {"room_id": "room-42"}

    websocket = WebSocket(starlette_websocket)

    assert websocket.path_params == {"room_id": "room-42"}
