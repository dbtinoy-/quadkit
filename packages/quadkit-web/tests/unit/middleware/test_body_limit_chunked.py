"""Tests: RequestBodySizeLimitMiddleware enforces the limit on chunked bodies."""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.middleware.body_limit import RequestBodySizeLimitMiddleware


def _app(max_body_size: int = 16) -> Starlette:
    async def echo(request: Request) -> JSONResponse:
        body = await request.body()
        return JSONResponse({"len": len(body)})

    app = Starlette(routes=[Route("/echo", endpoint=echo, methods=["POST"])])
    app.add_middleware(RequestBodySizeLimitMiddleware, max_body_size=max_body_size)
    return app


class TestBodyLimitChunked:
    def test_chunked_body_within_limit_ok(self) -> None:
        client = TestClient(_app(max_body_size=16), raise_server_exceptions=False)
        r = client.post(
            "/echo",
            content=b"1234567890",
            headers={"transfer-encoding": "chunked"},
        )
        assert r.status_code == 200

    def test_chunked_body_over_limit_rejected_413(self) -> None:
        client = TestClient(_app(max_body_size=16), raise_server_exceptions=False)
        r = client.post(
            "/echo",
            content=b"x" * 64,
            headers={"transfer-encoding": "chunked"},
        )
        assert r.status_code == 413

    def test_content_length_fast_path_still_413(self) -> None:
        client = TestClient(_app(max_body_size=16), raise_server_exceptions=False)
        r = client.post("/echo", content=b"x" * 64)
        assert r.status_code == 413

    @pytest.mark.asyncio
    async def test_streamed_over_limit_rejected_mid_stream(self) -> None:
        """Drive the middleware directly: a chunked stream past the limit
        aborts with 413 before the downstream app finishes reading."""

        events: list[dict] = []

        async def send(message: dict) -> None:
            events.append(message)

        chunks = [b"x" * 10, b"y" * 10]

        async def receive() -> dict:
            if chunks:
                chunk = chunks.pop(0)
                return {
                    "type": "http.request",
                    "body": chunk,
                    "more_body": bool(chunks),
                }
            return {"type": "http.request", "body": b"", "more_body": False}

        downstream_bytes = 0

        async def downstream(scope: dict, receive: Any, send: Any) -> None:
            nonlocal downstream_bytes
            while True:
                message = await receive()
                downstream_bytes += len(message.get("body", b""))
                if not message.get("more_body"):
                    break

        scope: dict = {
            "type": "http",
            "method": "POST",
            "path": "/echo",
            "headers": [[b"transfer-encoding", b"chunked"]],
        }
        middleware = RequestBodySizeLimitMiddleware(downstream, max_body_size=16)
        await middleware(scope, receive, send)

        start = [e for e in events if e["type"] == "http.response.start"]
        assert start and start[0]["status"] == 413
        assert downstream_bytes == 10