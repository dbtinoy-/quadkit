"""Round 26 hardening pins.

Covers the gap-hunt fixes from the quadkit-web audit:

- DIScopeMiddleware disposes the request scope even when the app raises
  (previously scoped resources leaked on every errored request) and a
  failing dispose never masks the request outcome.
- The SSE heartbeat loop survives a foreign error from one handler.
- SSE on_disconnect and websocket on_disconnect are best-effort (never
  mask the stream/connection outcome).
- WebSocket broadcast keeps going to the remaining connections when one
  send fails with a foreign error type.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from starlette.websockets import WebSocketDisconnect


class TestDIScopeDisposal:
    """Request-scoped resources must be disposed on the error path too."""

    def _scope(self) -> Any:
        scope = MagicMock()
        scope.dispose = AsyncMock()
        return scope

    def _middleware(self, app: Any, scope: Any) -> Any:
        from quadkit.web.middleware.di_scope import DIScopeMiddleware

        container = MagicMock()
        container.create_scope = MagicMock(return_value=scope)
        return DIScopeMiddleware(app=app, container=container)

    @staticmethod
    def _asgi_scope() -> dict[str, Any]:
        return {"type": "http", "headers": []}

    @pytest.mark.asyncio
    async def test_dispose_runs_when_app_raises(self) -> None:
        scope = self._scope()

        async def _broken_app(scope_: Any, receive: Any, send: Any) -> None:
            raise ValueError("handler exploded")

        middleware = self._middleware(_broken_app, scope)

        with pytest.raises(ValueError, match="handler exploded"):
            await middleware(self._asgi_scope(), None, None)

        scope.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_dispose_error_does_not_mask_request_error(self) -> None:
        scope = self._scope()
        scope.dispose = AsyncMock(
            side_effect=ExceptionGroup("dispose broke", [RuntimeError("x")])
        )

        async def _broken_app(scope_: Any, receive: Any, send: Any) -> None:
            raise ValueError("handler exploded")

        middleware = self._middleware(_broken_app, scope)

        with pytest.raises(ValueError, match="handler exploded"):
            await middleware(self._asgi_scope(), None, None)

    @pytest.mark.asyncio
    async def test_dispose_error_does_not_mask_success(self) -> None:
        scope = self._scope()
        # ExceptionGroup is what Scope.dispose() raises by design (collected
        # disposal errors) — the old tuple did not catch it.
        scope.dispose = AsyncMock(
            side_effect=ExceptionGroup("dispose broke", [RuntimeError("x")])
        )

        calls: list[str] = []

        async def _ok_app(scope_: Any, receive: Any, send: Any) -> None:
            calls.append("app")

        middleware = self._middleware(_ok_app, scope)

        await middleware(self._asgi_scope(), None, None)  # must not raise

        assert calls == ["app"]
        scope.dispose.assert_awaited_once()


class TestSSEHeartbeatIsolation:
    @pytest.mark.asyncio
    async def test_loop_survives_foreign_handler_error(self) -> None:
        from quadkit.web.sse.heartbeat import SSEHeartbeatScheduler

        class _Handler:
            def __init__(self, exc: Exception | None) -> None:
                self.exc = exc
                self.sent: list[str] = []

            async def send(self, event: str, data: str) -> None:
                if self.exc is not None:
                    raise self.exc
                self.sent.append(event)

        bad = _Handler(ValueError("handler exploded"))
        good = _Handler(None)

        scheduler = SSEHeartbeatScheduler(interval=0.0, tick_resolution=0.01)
        await scheduler.register(bad)
        await scheduler.register(good)
        await asyncio.sleep(0.08)
        await scheduler.stop()

        assert good.sent  # the loop survived the bad handler and kept firing


class TestSSEDisconnectBestEffort:
    @pytest.mark.asyncio
    async def test_on_disconnect_error_suppressed(self) -> None:
        from quadkit.web.sse.handler import AbstractSSEHandler

        class _SSE(AbstractSSEHandler):
            async def stream(self, request: Any) -> Any:
                yield {"data": "x"}

            async def on_disconnect(self, request: Any) -> None:
                raise ValueError("disconnect boom")

        handler = _SSE()

        # Exhausting the generator must not propagate the disconnect error.
        async for _ in handler._create_event_generator(MagicMock()):
            pass


class TestWebSocketHardening:
    def _handler_cls(self) -> type:
        from quadkit.web.websocket.handler import AbstractWebSocketHandler

        class _WS(AbstractWebSocketHandler):
            async def on_connect(self, websocket: Any) -> None:
                await websocket.accept()

            async def on_message(self, websocket: Any, message: Any) -> None:
                pass

            async def on_disconnect(self, websocket: Any) -> None:
                raise ValueError("disconnect boom")

        return _WS

    @pytest.mark.asyncio
    async def test_broadcast_survives_foreign_send_error(self) -> None:
        handler = self._handler_cls()()

        ws1 = MagicMock()
        ws1.send_json = AsyncMock()
        ws_bad = MagicMock()
        ws_bad.send_json = AsyncMock(side_effect=ValueError("send boom"))
        ws2 = MagicMock()
        ws2.send_json = AsyncMock()
        handler._connections = {ws1, ws_bad, ws2}

        await handler.broadcast({"a": 1})  # must not raise

        ws1.send_json.assert_awaited_once()
        ws2.send_json.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_disconnect_error_suppressed(self) -> None:
        handler = self._handler_cls()()

        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.receive_json = AsyncMock(side_effect=WebSocketDisconnect())

        await handler.handle(ws)  # must not raise

        assert ws not in handler._connections
