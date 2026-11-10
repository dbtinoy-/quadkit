"""Live-server regression tests for the async runner (SERVER-1).

The unit suite fakes every backend, which is how an unconditional crash
shipped: mocked ``Granian.serve()`` cannot raise the ``ValueError`` the
real one raises when signal handlers are installed off the main thread.
These tests drive the *real* servers through ``run_server_async`` with a
minimal ASGI app, probe them over a socket, and shut them down by
cancelling the serving task — the in-loop contract. Each test skips
when its backend is not installed (backends are optional extras; they
are in the ``test`` extra so package CI exercises them for real).

The sync multiprocess path (``run_server`` + Granian supervisor) is not
covered here: it blocks the main thread by design and can only be
stopped by a signal, which a test process must not send itself. The
CLI's subprocess server registry covers that shape in quadkit-cli.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import socket
from typing import Any
from unittest.mock import patch

import httpx
import pytest

pytestmark = pytest.mark.integration


async def _asgi_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    elif scope["type"] == "http":
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"text/plain"]],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _serve_and_probe(backend: str) -> None:
    from quadkit.web.server import run_server_async

    port = _free_port()
    with patch(
        "quadkit.web.server.runner._resolve_backend", return_value=backend
    ):
        task = asyncio.create_task(
            run_server_async(_asgi_app, host="127.0.0.1", port=port)
        )
        try:
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{port}", timeout=2.0
            ) as http:
                for _ in range(60):
                    if task.done():
                        raise AssertionError(
                            f"{backend} exited before serving: {task.exception()!r}"
                        )
                    try:
                        response = await http.get("/")
                        break
                    except httpx.HTTPError:
                        await asyncio.sleep(0.25)
                else:  # pragma: no cover - loop-else only on timeout
                    raise AssertionError(f"{backend} never answered on port {port}")
            assert response.status_code == 200
            assert response.text == "ok"
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=15)


@pytest.mark.skipif(
    importlib.util.find_spec("granian") is None, reason="granian not installed"
)
async def test_granian_embedded_serves_and_stops() -> None:
    """The SERVER-1 scenario: Granian via run_server_async must start."""
    await _serve_and_probe("granian")


@pytest.mark.skipif(
    importlib.util.find_spec("uvicorn") is None, reason="uvicorn not installed"
)
async def test_uvicorn_serves_and_stops() -> None:
    await _serve_and_probe("uvicorn")


@pytest.mark.skipif(
    importlib.util.find_spec("hypercorn") is None, reason="hypercorn not installed"
)
async def test_hypercorn_serves_and_stops() -> None:
    await _serve_and_probe("hypercorn")
