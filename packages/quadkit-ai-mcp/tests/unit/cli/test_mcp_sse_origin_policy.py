"""Origin-policy tests for the MCP SSE transport (round-4 finding).

The SSE transport is a bare-asyncio HTTP server bound to loopback.  It
previously answered ``Access-Control-Allow-Origin: *`` with no Origin
validation, so any webpage the user visited could POST JSON-RPC bodies
as ``text/plain`` (no CORS preflight) to drive the local MCP server and
read its responses.  The handler now denies non-loopback origins (403)
and echoes the allowed origin instead of ``*``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from quadkit.ai.mcp.cli.commands import _handle_http_connection, _is_loopback_origin


class _StubMCPServer:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(message)
        return {
            "jsonrpc": "2.0",
            "result": "pong",
            "id": message.get("id"),
        }


class _FakeWriter:
    def __init__(self) -> None:
        self.buffer = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.buffer += data

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        pass


async def _roundtrip(raw_request: bytes, server: _StubMCPServer) -> bytes:
    reader = asyncio.StreamReader()
    reader.feed_data(raw_request)
    reader.feed_eof()
    writer = _FakeWriter()
    await _handle_http_connection(reader, writer, server)
    return bytes(writer.buffer)


def _post(body: str, origin: str | None) -> bytes:
    headers = [
        "POST /mcp HTTP/1.1",
        "Host: 127.0.0.1",
        "Content-Type: text/plain;charset=UTF-8",
        f"Content-Length: {len(body)}",
    ]
    if origin is not None:
        headers.append(f"Origin: {origin}")
    return ("\r\n".join(headers) + "\r\n\r\n" + body).encode()


def _options(origin: str) -> bytes:
    return (
        "OPTIONS /mcp HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        f"Origin: {origin}\r\n"
        "Access-Control-Request-Method: POST\r\n"
        "Access-Control-Request-Headers: content-type\r\n"
        "\r\n\r\n"
    ).encode()


# --- pure helper ---


@pytest.mark.parametrize(
    "origin",
    [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://[::1]:5173",
    ],
)
def test_is_loopback_origin_accepts_loopback(origin: str) -> None:
    assert _is_loopback_origin(origin) is True


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "https://192.168.1.10",
        "null",
        "",
        "not a url",
    ],
)
def test_is_loopback_origin_denies_foreign(origin: str) -> None:
    assert _is_loopback_origin(origin) is False


# --- handler behavior ---


@pytest.mark.asyncio
async def test_cross_origin_webpage_denied_and_not_invoked() -> None:
    server = _StubMCPServer()
    response = await _roundtrip(
        _post('{"jsonrpc":"2.0","method":"tools/call","id":1}', "https://evil.example"),
        server,
    )
    assert response.startswith(b"HTTP/1.1 403")
    assert b"Access-Control-Allow-Origin" not in response
    assert server.calls == []


@pytest.mark.asyncio
async def test_loopback_origin_accepted_and_echoed() -> None:
    server = _StubMCPServer()
    response = await _roundtrip(
        _post(
            '{"jsonrpc":"2.0","method":"tools/call","id":2}', "http://localhost:5173"
        ),
        server,
    )
    assert response.startswith(b"HTTP/1.1 200")
    assert b"Access-Control-Allow-Origin: http://localhost:5173" in response
    assert b"Vary: Origin" in response
    assert b"Access-Control-Allow-Origin: *" not in response
    assert len(server.calls) == 1


@pytest.mark.asyncio
async def test_no_origin_client_works_without_cors_headers() -> None:
    server = _StubMCPServer()
    response = await _roundtrip(
        _post('{"jsonrpc":"2.0","method":"tools/call","id":3}', None),
        server,
    )
    assert response.startswith(b"HTTP/1.1 200")
    assert b"Access-Control-Allow-Origin" not in response
    assert b'"result":"pong"' in response


@pytest.mark.asyncio
async def test_options_preflight_ok_for_loopback_origin() -> None:
    server = _StubMCPServer()
    response = await _roundtrip(_options("http://127.0.0.1:8001"), server)
    assert response.startswith(b"HTTP/1.1 204")
    assert b"Access-Control-Allow-Origin: http://127.0.0.1:8001" in response
    assert b"Access-Control-Allow-Methods: POST, OPTIONS" in response
    assert server.calls == []


@pytest.mark.asyncio
async def test_options_preflight_denied_for_foreign_origin() -> None:
    server = _StubMCPServer()
    response = await _roundtrip(_options("https://evil.example"), server)
    assert response.startswith(b"HTTP/1.1 403")
    assert b"Access-Control-Allow-Origin" not in response


@pytest.mark.asyncio
async def test_null_origin_denied() -> None:
    server = _StubMCPServer()
    response = await _roundtrip(
        _post('{"jsonrpc":"2.0","method":"tools/call","id":4}', "null"),
        server,
    )
    assert response.startswith(b"HTTP/1.1 403")
    assert server.calls == []


@pytest.mark.asyncio
async def test_malformed_json_still_400() -> None:
    server = _StubMCPServer()
    response = await _roundtrip(_post("{not json", "http://localhost:5173"), server)
    assert response.startswith(b"HTTP/1.1 400")
    assert server.calls == []


@pytest.mark.asyncio
async def test_capitalized_header_names_parsed_case_insensitively() -> None:
    """curl / http.client send 'Content-Length:' — must not 404."""
    server = _StubMCPServer()
    response = await _roundtrip(
        _post(
            '{"jsonrpc":"2.0","method":"tools/call","id":5}', "http://127.0.0.1:8001"
        ),
        server,
    )
    assert response.startswith(b"HTTP/1.1 200")
    assert b'"result":"pong"' in response
    assert len(server.calls) == 1
