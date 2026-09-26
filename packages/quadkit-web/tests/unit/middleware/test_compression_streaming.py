"""CompressionMiddleware must not buffer streamed responses.

The middleware compresses whole bodies, which means it holds every chunk until
the response ends. That is fine for JSON and fatal for SSE: a client would not
see a byte until the model had finished generating. Streamed content types pass
through untouched, chunk by chunk.
"""

from __future__ import annotations

import gzip
from typing import Any

import pytest

from quadkit.web.middleware.compression import CompressionMiddleware


class _Recorder:
    """ASGI ``send`` that keeps every message the middleware emits."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def __call__(self, message: dict[str, Any]) -> None:
        self.messages.append(message)

    @property
    def bodies(self) -> list[bytes]:
        return [
            m.get("body", b"")
            for m in self.messages
            if m["type"] == "http.response.body"
        ]


def _scope(accept_encoding: str) -> dict[str, Any]:
    return {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [(b"accept-encoding", accept_encoding.encode())],
    }


async def _receive() -> dict[str, Any]:  # pragma: no cover - never awaited
    return {"type": "http.request", "body": b"", "more_body": False}


async def _sse_app(recorder: _Recorder) -> Any:
    """Inner app: an SSE response of four chunks, checked mid-flight."""

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/event-stream"),
                    (b"cache-control", b"no-cache"),
                ],
            }
        )
        for index in range(4):
            # The client must already be able to see the previous chunks: if the
            # middleware were buffering, nothing would have been forwarded yet.
            assert len(recorder.bodies) == index, (
                f"chunk {index} was held back by the middleware"
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"data: chunk\n\n",
                    "more_body": True,
                }
            )
        await send(
            {
                "type": "http.response.body",
                "body": b"data: [DONE]\n\n",
                "more_body": False,
            }
        )

    return app


@pytest.mark.asyncio
async def test_sse_chunks_are_forwarded_as_they_are_produced() -> None:
    recorder = _Recorder()
    middleware = CompressionMiddleware(await _sse_app(recorder))

    await middleware(_scope("gzip, deflate"), _receive, recorder)

    assert len(recorder.bodies) == 5
    assert recorder.bodies[0] == b"data: chunk\n\n"
    assert recorder.bodies[-1] == b"data: [DONE]\n\n"
    assert not any(
        m.get("headers") for m in recorder.messages if m["type"] == "http.response.body"
    )


@pytest.mark.asyncio
async def test_sse_response_is_not_gzipped() -> None:
    recorder = _Recorder()
    middleware = CompressionMiddleware(await _sse_app(recorder))

    await middleware(_scope("gzip"), _receive, recorder)

    start = next(m for m in recorder.messages if m["type"] == "http.response.start")
    headers = {k.decode(): v.decode() for k, v in start["headers"]}
    assert headers["content-type"] == "text/event-stream"
    assert "content-encoding" not in headers


@pytest.mark.asyncio
async def test_json_bodies_are_still_compressed() -> None:
    """The pass-through must not disable compression for normal responses."""

    recorder = _Recorder()
    payload = b'{"detail": "' + b"x" * 4000 + b'"}'

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": payload, "more_body": False})

    middleware = CompressionMiddleware(app)
    await middleware(_scope("gzip, deflate"), _receive, recorder)

    start = next(m for m in recorder.messages if m["type"] == "http.response.start")
    headers = {k.decode(): v.decode() for k, v in start["headers"]}
    assert headers.get("content-encoding") == "gzip"
    assert gzip.decompress(recorder.bodies[0]) == payload


@pytest.mark.asyncio
async def test_identity_clients_keep_the_fast_path() -> None:
    """No gzip in Accept-Encoding: the app is not wrapped at all."""

    recorder = _Recorder()
    calls: list[str] = []

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        calls.append("called")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"plain", "more_body": False})

    middleware = CompressionMiddleware(app)
    await middleware(_scope("identity"), _receive, recorder)

    assert calls == ["called"]
    assert recorder.bodies == [b"plain"]
