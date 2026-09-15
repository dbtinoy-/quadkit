"""Unit tests for web hook middleware emission."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.hooks import HookRegistry
from quadkit.web.hooks import WebRequestReceivedHook, WebResponsePreparedHook
from quadkit.web.middleware.hooks import WebHooksMiddleware


class TestWebHooksMiddleware:
    """Verify HTTP request/response hook emission."""

    def test_http_request_emits_request_and_response_hooks(self) -> None:
        """HTTP requests emit the canonical web hook payloads."""
        received: list[object] = []
        prepared: list[object] = []
        registry = HookRegistry("web-test")

        async def capture_received(*, payload: object) -> None:
            received.append(payload)

        async def capture_prepared(*, payload: object) -> None:
            prepared.append(payload)

        registry.register_action("request.received", capture_received)
        registry.register_action("response.prepared", capture_prepared)

        async def homepage(_request):
            return JSONResponse({"ok": True}, status_code=201)

        app = Starlette(routes=[Route("/hooks", homepage, methods=["POST"])])
        app.add_middleware(WebHooksMiddleware, hooks=registry)

        with TestClient(app) as client:
            response = client.post("/hooks")

        assert response.status_code == 201
        assert received == [
            WebRequestReceivedHook(path="/hooks", method="POST"),
        ]
        assert prepared == [
            WebResponsePreparedHook(path="/hooks", status_code=201),
        ]
