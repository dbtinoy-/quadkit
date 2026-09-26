"""A generated WebSocket handler, mounted and driven over a real client.

`QUADKIT_FRAMEWORK_BUGS.md` WS-1 and WS-3 were both "the generated handler is
inert or crashes" defects, and both are only observable through the transport:

* WS-1 — a standalone ``@websocket_handler`` class was never mounted by the
  normal provider path (the decorator only stamps metadata);
* WS-3 — the generated handler reads ``websocket.path_params``, which the
  transport wrapper did not offer, so the first line of ``on_connect`` raised.

The handler is generated here rather than hand-written, because a hand-written
stand-in would keep passing while the template drifted.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest
from starlette.applications import Starlette
from starlette.routing import WebSocketRoute
from starlette.testclient import TestClient

from quadkit.web.cli.generators.websocket import WebSocketHandlerGenerator
from quadkit.web.routing.discovery import discover_websocket_handlers
from quadkit.web.routing.route_handlers import _wrap_websocket_handler


def _generated_handler(tmp_path: Path, module_name: str = "chat_socket") -> type:
    """Generate a handler, import it, and return the class."""
    package = tmp_path / "gen_ws_pkg"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("")
    result = WebSocketHandlerGenerator(output_dir=package).generate("chat_socket")
    path = Path(result.files_created[0])

    spec = importlib.util.spec_from_file_location(
        f"{module_name}_module", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.ChatSocket


def _client(tmp_path: Path, handler: type, path: str) -> TestClient:
    app = Starlette(routes=[])
    app.router.routes.append(WebSocketRoute(path, _wrap_websocket_handler(handler)))
    return TestClient(app)


def test_the_generated_handler_mounts_and_accepts_a_connection(tmp_path: Path) -> None:
    """The handler's ``on_connect`` runs, including its ``path_params`` read."""
    handler = _generated_handler(tmp_path)

    with _client(tmp_path, handler, "/ws/chat_socket").websocket_connect(
        "/ws/chat_socket"
    ) as websocket:
        # ``on_connect`` accepts; a rejection would raise on connect instead.
        websocket.send_json({"hello": "room"})
        assert websocket.receive_json() == {"hello": "room"}


def test_a_path_parameter_reaches_the_handler(tmp_path: Path) -> None:
    """``{room_id}`` in the route is visible to the generated room logic."""
    handler = _generated_handler(tmp_path)

    with _client(tmp_path, handler, "/ws/chat_socket/{room_id}").websocket_connect(
        "/ws/chat_socket/lobby"
    ) as websocket:
        assert "lobby" in handler.rooms
        websocket.send_json({"room": "lobby"})
        assert websocket.receive_json() == {"room": "lobby"}

    assert handler.rooms.get("lobby") == set()


def test_discovery_finds_a_decorated_handler(tmp_path: Path, monkeypatch) -> None:
    """WS-1: the decorator's metadata is what discovery scans for."""
    _generated_handler(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    found = discover_websocket_handlers(("gen_ws_pkg",))

    assert [cls.__name__ for cls in found] == ["ChatSocket"]
