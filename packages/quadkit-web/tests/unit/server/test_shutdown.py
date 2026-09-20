"""Tests for GracefulShutdownManager and ShutdownMiddleware."""
from __future__ import annotations

import asyncio
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.server.shutdown import GracefulShutdownManager, ShutdownMiddleware


class TestGracefulShutdownManager:
    def test_initial_state(self) -> None:
        manager = GracefulShutdownManager()
        assert manager.is_shutting_down is False
        assert manager.active_connections == 0

    def test_begin_shutdown_sets_flag(self) -> None:
        manager = GracefulShutdownManager()
        manager.begin_shutdown()
        assert manager.is_shutting_down is True

    def test_complete_shutdown_sets_drain_event(self) -> None:
        manager = GracefulShutdownManager()
        manager._drain_event = asyncio.Event()
        manager.complete_shutdown()
        assert manager._drain_event.is_set()

    @pytest.mark.asyncio
    async def test_track_connection_increments_and_decrements(self) -> None:
        manager = GracefulShutdownManager()
        assert manager.active_connections == 0
        async with manager.track_connection():
            assert manager.active_connections == 1
        assert manager.active_connections == 0

    @pytest.mark.asyncio
    async def test_track_connection_signals_drain_when_last_exits(self) -> None:
        manager = GracefulShutdownManager()
        manager._drain_event = asyncio.Event()
        manager.begin_shutdown()

        async with manager.track_connection():
            pass

        assert manager._drain_event.is_set()

    @pytest.mark.asyncio
    async def test_begin_shutdown_signals_drain_when_no_connections(self) -> None:
        manager = GracefulShutdownManager()
        manager._drain_event = asyncio.Event()
        manager.begin_shutdown()
        assert manager._drain_event.is_set()

    @pytest.mark.asyncio
    async def test_wait_for_drain_times_out(self) -> None:
        manager = GracefulShutdownManager(timeout=0.01)
        # drain event never set → should time out gracefully
        await manager.wait_for_drain()  # should not raise

    @pytest.mark.asyncio
    async def test_wait_for_drain_completes_when_signalled(self) -> None:
        manager = GracefulShutdownManager(timeout=5.0)
        manager._drain_event = asyncio.Event()
        manager._drain_event.set()
        await manager.wait_for_drain()  # should return immediately

    @pytest.mark.asyncio
    async def test_serve_503_returns_503(self) -> None:
        manager = GracefulShutdownManager()
        response = await manager.serve_503_during_drain(None)
        assert response.status_code == 503


class TestShutdownMiddleware:
    def test_normal_request_passes_through(self) -> None:
        async def homepage(request):
            return JSONResponse({"ok": True})

        manager = GracefulShutdownManager()
        inner = Starlette(routes=[Route("/", homepage)])
        client = TestClient(ShutdownMiddleware(inner, manager))
        response = client.get("/")
        assert response.status_code == 200

    def test_request_during_shutdown_returns_503(self) -> None:
        async def homepage(request):
            return JSONResponse({"ok": True})

        manager = GracefulShutdownManager()
        manager.begin_shutdown()
        inner = Starlette(routes=[Route("/", homepage)])
        client = TestClient(ShutdownMiddleware(inner, manager), raise_server_exceptions=False)
        response = client.get("/")
        assert response.status_code == 503
