"""Tests for CORSMiddleware — including P1-1: Vary: Origin header.

Adapted from quadkit-security test suite; imports updated to
quadkit.web.security.* after HTTP middleware absorption in Task 3.
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.web.security.config import CORSConfig
from quadkit.web.security.cors.middleware import CORSMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scope(
    method: str = "GET",
    path: str = "/api/data",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict[str, Any]:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
    }


def _make_app() -> Any:
    """Return a minimal no-op ASGI app that sends a 200 response."""

    async def _app(scope: Any, receive: Any, send: Any) -> None:  # noqa: ARG001
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    return _app


async def _run(
    middleware: CORSMiddleware,
    scope: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run middleware and collect all sent messages."""
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(msg: dict[str, Any]) -> None:
        messages.append(msg)

    await middleware(scope, receive, send)
    return messages


def _header_map(messages: list[dict[str, Any]]) -> dict[str, str]:
    """Extract response-start headers into a normalised lower-case dict."""
    for msg in messages:
        if msg.get("type") == "http.response.start":
            return {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in msg.get("headers", [])
            }
    return {}


# ---------------------------------------------------------------------------
# P1-1: Vary: Origin — specific origin (non-wildcard)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_specific_origin_response_includes_vary_origin() -> None:
    """P1-1: Origin-specific CORS responses must include Vary: Origin."""
    config = CORSConfig(
        allowed_origins=["https://example.com"],
        allow_credentials=False,
    )
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="GET",
        headers=[(b"origin", b"https://example.com")],
    )
    messages = await _run(middleware, scope)
    headers = _header_map(messages)

    assert "access-control-allow-origin" in headers, "CORS header missing"
    assert headers["access-control-allow-origin"] == "https://example.com"
    assert "vary" in headers, "Vary header missing on specific-origin CORS response"
    assert "origin" in headers["vary"].lower(), (
        f"Vary header must contain 'Origin', got: {headers['vary']!r}"
    )


@pytest.mark.asyncio
async def test_cors_specific_origin_with_credentials_includes_vary_origin() -> None:
    """P1-1: Credentialed CORS responses must include Vary: Origin."""
    config = CORSConfig(
        allowed_origins=["https://app.internal"],
        allow_credentials=True,
    )
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="GET",
        headers=[(b"origin", b"https://app.internal")],
    )
    messages = await _run(middleware, scope)
    headers = _header_map(messages)

    assert headers.get("access-control-allow-credentials") == "true"
    assert "vary" in headers, "Vary header missing on credentialed CORS response"
    assert "origin" in headers["vary"].lower()


# ---------------------------------------------------------------------------
# P1-1: Vary: Origin — preflight (OPTIONS) with specific origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_preflight_specific_origin_includes_vary_origin() -> None:
    """P1-1: Preflight responses for specific origins must include Vary: Origin."""
    config = CORSConfig(
        allowed_origins=["https://example.com"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="OPTIONS",
        headers=[
            (b"origin", b"https://example.com"),
            (b"access-control-request-method", b"POST"),
        ],
    )
    messages = await _run(middleware, scope)
    headers = _header_map(messages)

    start_msg = next(m for m in messages if m.get("type") == "http.response.start")
    assert start_msg["status"] == 204
    assert headers.get("access-control-allow-origin") == "https://example.com"
    assert "vary" in headers, "Vary header missing on preflight CORS response"
    assert "origin" in headers["vary"].lower()


# ---------------------------------------------------------------------------
# Wildcard origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_wildcard_origin_allows_request_without_error() -> None:
    """Wildcard CORS config must process requests without raising."""
    config = CORSConfig(
        allowed_origins=["*"],
        allow_credentials=False,
    )
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="GET",
        headers=[(b"origin", b"https://any-origin.example.com")],
    )
    messages = await _run(middleware, scope)
    headers = _header_map(messages)

    assert headers.get("access-control-allow-origin") == "*", (
        "Wildcard config must return ACAO: *"
    )
    if "vary" in headers:
        assert "origin" in headers["vary"].lower()


# ---------------------------------------------------------------------------
# No CORS headers for disallowed origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disallowed_origin_receives_no_cors_headers() -> None:
    """Disallowed origins must receive no CORS headers at all."""
    config = CORSConfig(allowed_origins=["https://allowed.example.com"])
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="GET",
        headers=[(b"origin", b"https://evil.example.com")],
    )
    messages = await _run(middleware, scope)
    headers = _header_map(messages)

    assert "access-control-allow-origin" not in headers
    assert "vary" not in headers


# ---------------------------------------------------------------------------
# P2-cors-headers: Access-Control-Request-Headers validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_preflight_rejects_disallowed_request_headers() -> None:
    """P2-cors-headers: preflight with unlisted request headers must return 403."""
    config = CORSConfig(
        allowed_origins=["https://example.com"],
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "authorization"],
    )
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="OPTIONS",
        headers=[
            (b"origin", b"https://example.com"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type, x-evil-header"),
        ],
    )
    messages = await _run(middleware, scope)
    start_msg = next(m for m in messages if m.get("type") == "http.response.start")
    assert start_msg["status"] == 403, (
        f"Expected 403 for disallowed request header, got {start_msg['status']}"
    )


@pytest.mark.asyncio
async def test_cors_preflight_accepts_all_listed_request_headers() -> None:
    """P2-cors-headers: preflight with all headers in allowlist must return 204."""
    config = CORSConfig(
        allowed_origins=["https://example.com"],
        allow_methods=["GET", "POST"],
        allow_headers=["content-type", "authorization"],
    )
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="OPTIONS",
        headers=[
            (b"origin", b"https://example.com"),
            (b"access-control-request-method", b"POST"),
            (b"access-control-request-headers", b"content-type, authorization"),
        ],
    )
    messages = await _run(middleware, scope)
    start_msg = next(m for m in messages if m.get("type") == "http.response.start")
    assert start_msg["status"] == 204, (
        f"Expected 204 for allowed headers, got {start_msg['status']}"
    )


@pytest.mark.asyncio
async def test_cors_preflight_wildcard_allow_headers_accepts_any() -> None:
    """P2-cors-headers: allow_headers=['*'] accepts any request header."""
    config = CORSConfig(
        allowed_origins=["https://example.com"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    middleware = CORSMiddleware(app=_make_app(), config=config)

    scope = _make_scope(
        method="OPTIONS",
        headers=[
            (b"origin", b"https://example.com"),
            (b"access-control-request-method", b"GET"),
            (b"access-control-request-headers", b"x-custom-header, x-another"),
        ],
    )
    messages = await _run(middleware, scope)
    start_msg = next(m for m in messages if m.get("type") == "http.response.start")
    assert start_msg["status"] == 204, (
        f"Wildcard allow_headers must accept any header, got {start_msg['status']}"
    )
