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
        assert start
        assert start[0]["status"] == 413
        assert downstream_bytes == 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers", [[], [[b"content-length", b"1"]], [[b"content-length", b"invalid"]]]
)
async def test_oversized_body_cannot_continue_downstream_or_emit_two_responses(headers):
    """An incomplete body must not be turned into a successful empty request."""
    events = []
    effects = []
    chunks = [b"x" * 8, b"y" * 9, b"later"]

    async def receive():
        chunk = chunks.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}

    async def send(message):
        events.append(message)

    async def downstream(scope, receive, send):
        request = Request(scope, receive)
        try:
            await request.body()
        except Exception:
            # Ordinary error handling cannot make an aborted request valid.
            effects.append("caught ordinary exception")
        effects.append("mutated")
        await JSONResponse({"success": True})(scope, receive, send)

    scope = {"type": "http", "method": "POST", "path": "/write", "headers": headers}
    await RequestBodySizeLimitMiddleware(downstream, max_body_size=16)(
        scope, receive, send
    )
    assert effects == []
    assert [m["status"] for m in events if m["type"] == "http.response.start"] == [413]
    assert len([m for m in events if m["type"] == "http.response.body"]) == 1
    assert chunks == [b"later"]


@pytest.mark.asyncio
async def test_exact_boundary_remains_streaming_and_succeeds():
    chunks = [b"12345678", b"abcdefgh"]
    events = []
    consumed = []

    async def receive():
        chunk = chunks.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}

    async def send(message):
        events.append(message)

    async def downstream(scope, receive, send):
        first = await receive()
        consumed.append(first["body"])
        assert chunks == [b"abcdefgh"]  # middleware has not eagerly buffered it
        second = await receive()
        consumed.append(second["body"])
        await JSONResponse({"ok": True})(scope, receive, send)

    scope = {"type": "http", "method": "POST", "path": "/", "headers": []}
    await RequestBodySizeLimitMiddleware(downstream, 16)(scope, receive, send)
    assert consumed == [b"12345678", b"abcdefgh"]
    assert [m["status"] for m in events if m["type"] == "http.response.start"] == [200]


@pytest.mark.asyncio
async def test_declared_oversize_rejected_without_invoking_app_or_reading_body():
    calls = []
    events = []

    async def receive():
        calls.append("receive")
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        events.append(message)

    async def downstream(scope, receive, send):
        calls.append("app")

    scope = {"type": "http", "path": "/", "headers": [(b"content-length", b"17")]}
    await RequestBodySizeLimitMiddleware(downstream, 16)(scope, receive, send)
    assert calls == []
    assert [m["status"] for m in events if m["type"] == "http.response.start"] == [413]


@pytest.mark.asyncio
@pytest.mark.parametrize("send_response", [False, True])
async def test_caught_base_exception_cannot_produce_success_response(send_response):
    events = []

    async def receive():
        return {"type": "http.request", "body": b"x" * 17, "more_body": False}

    async def send(message):
        events.append(message)

    async def downstream(scope, receive, send):
        try:
            await receive()
        except BaseException:
            pass  # Simulate a misbehaving app; its side effects cannot be undone.
        if send_response:
            await JSONResponse({"success": True})(scope, receive, send)

    scope = {"type": "http", "path": "/", "headers": []}
    await RequestBodySizeLimitMiddleware(downstream, 16)(scope, receive, send)
    assert [m["status"] for m in events if m["type"] == "http.response.start"] == [413]


@pytest.mark.asyncio
async def test_already_started_response_is_not_followed_by_a_second_start():
    from quadkit.web.middleware.body_limit import _BodyLimitExceeded  # noqa: PLC2701

    events = []

    async def receive():
        return {"type": "http.request", "body": b"x" * 17, "more_body": False}

    async def send(message):
        events.append(message)

    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await receive()

    scope = {"type": "http", "path": "/", "headers": []}
    with pytest.raises(_BodyLimitExceeded):
        await RequestBodySizeLimitMiddleware(downstream, 16)(scope, receive, send)
    assert [m["status"] for m in events if m["type"] == "http.response.start"] == [200]


@pytest.mark.asyncio
async def test_unrelated_errors_and_cancellation_are_not_rewritten():
    import asyncio

    scope = {"type": "http", "path": "/", "headers": []}
    events = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        events.append(message)

    for exc in (ValueError("broken"), asyncio.CancelledError()):

        async def downstream(scope, receive, send):
            raise exc

        with pytest.raises(type(exc)):
            await RequestBodySizeLimitMiddleware(downstream, 16)(scope, receive, send)
    assert events == []


@pytest.mark.asyncio
async def test_body_abort_through_starlette_task_group_middleware():
    import asyncio

    from starlette.middleware.base import BaseHTTPMiddleware

    events = []
    effects = []
    chunks = [b"x" * 8, b"y" * 9]

    async def receive():
        if chunks:
            chunk = chunks.pop(0)
            return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}
        await asyncio.Event().wait()
        return {"type": "http.disconnect"}

    async def send(message):
        events.append(message)

    async def endpoint(request):
        await request.body()
        effects.append("mutated")
        return JSONResponse({"ok": True})

    class PassThrough(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            return await call_next(request)

    app = Starlette(routes=[Route("/write", endpoint, methods=["POST"])])
    app.add_middleware(PassThrough)
    wrapped = RequestBodySizeLimitMiddleware(app, 16)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/write",
        "headers": [],
        "query_string": b"",
    }
    await asyncio.wait_for(wrapped(scope, receive, send), timeout=3)
    assert effects == []
    assert [m["status"] for m in events if m["type"] == "http.response.start"] == [413]


@pytest.mark.asyncio
async def test_grouped_body_abort_is_handled_but_mixed_group_is_not_masked():
    events = []

    async def receive():
        return {"type": "http.request", "body": b"x" * 17, "more_body": False}

    async def send(message):
        events.append(message)

    async def downstream(scope, receive, send):
        try:
            await receive()
        except BaseException as exc:
            raise BaseExceptionGroup("wrapped", [exc]) from exc

    scope = {"type": "http", "path": "/", "headers": []}
    await RequestBodySizeLimitMiddleware(downstream, 16)(scope, receive, send)
    assert [m["status"] for m in events if m["type"] == "http.response.start"] == [413]
    events.clear()

    async def mixed(scope, receive, send):
        try:
            await receive()
        except BaseException as exc:
            raise BaseExceptionGroup("mixed", [exc, ValueError("unrelated")]) from exc

    with pytest.raises(BaseExceptionGroup, match="mixed"):
        await RequestBodySizeLimitMiddleware(mixed, 16)(scope, receive, send)
    assert events == []
