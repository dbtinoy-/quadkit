"""Integration tests for the full HTTP security middleware stack.

Adapted from quadkit-security integration tests; imports updated to
quadkit.web.security.* after HTTP middleware absorption in Task 3.

GuardChain stays in quadkit.security (core); HTTP middleware classes
move to quadkit.web.security.*.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from quadkit.contracts.exceptions.middleware import MiddlewareGuardError
from quadkit.security.guards.chain import GuardChainImpl as GuardChain
from quadkit.web.security.config import (
    CORSConfig,
    CSRFConfig,
)
from quadkit.web.security.cors.middleware import CORSMiddleware
from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

# ---------------------------------------------------------------------------
# ASGI test helpers
# ---------------------------------------------------------------------------


def _make_scope(
    method: str = "GET",
    path: str = "/",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict[str, Any]:
    """Build a minimal ASGI HTTP scope."""
    return {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
        "query_string": b"",
    }


async def _receive() -> dict[str, Any]:
    """Stub ASGI receive callable."""
    return {"type": "http.request", "body": b"", "more_body": False}


class _Collector:
    """Captures all ASGI messages sent by middleware during a request."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send(self, message: dict[str, Any]) -> None:
        """Capture an outgoing ASGI message."""
        self.messages.append(message)

    def response_headers(self) -> dict[str, str]:
        """Extract the response headers from a http.response.start message."""
        for msg in self.messages:
            if msg.get("type") == "http.response.start":
                return {k.decode(): v.decode() for k, v in msg.get("headers", [])}
        return {}

    def status(self) -> int | None:
        """Return the HTTP status code from the response, if present."""
        for msg in self.messages:
            if msg.get("type") == "http.response.start":
                return msg.get("status")
        return None


async def _bare_asgi_app(
    scope: dict[str, Any],
    receive: Callable[[], Awaitable[dict[str, Any]]],
    send: Callable[[dict[str, Any]], Awaitable[None]],
) -> None:
    """Minimal ASGI endpoint — always returns 200 OK."""
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


# ---------------------------------------------------------------------------
# Stub GuardProtocol implementations
# ---------------------------------------------------------------------------


class _AllowGuard:
    """GuardProtocol that unconditionally allows every request."""

    async def can_activate(self, context: dict[str, Any]) -> bool:
        """Always returns True."""
        return True


class _DenyGuard:
    """GuardProtocol that unconditionally denies every request."""

    async def can_activate(self, context: dict[str, Any]) -> bool:
        """Always returns False."""
        return False


# ---------------------------------------------------------------------------
# CORSMiddleware (ASGI integration)
# ---------------------------------------------------------------------------


class TestCORSMiddlewareIntegration:
    """Integration tests for CORSMiddleware ASGI implementation."""

    async def test_allowed_origin_returns_cors_headers(self) -> None:
        config = CORSConfig(allowed_origins=["https://example.com"])
        middleware = CORSMiddleware(_bare_asgi_app, config)
        collector = _Collector()
        scope = _make_scope(
            method="GET",
            headers=[(b"origin", b"https://example.com")],
        )

        await middleware(scope, _receive, collector.send)

        assert collector.status() == 200
        assert "Access-Control-Allow-Origin" in collector.response_headers()

    async def test_options_preflight_returns_204(self) -> None:
        config = CORSConfig(
            allowed_origins=["https://example.com"],
            allow_methods=["GET", "POST"],
        )
        middleware = CORSMiddleware(_bare_asgi_app, config)
        collector = _Collector()
        scope = _make_scope(
            method="OPTIONS",
            headers=[
                (b"origin", b"https://example.com"),
                (b"access-control-request-method", b"POST"),
            ],
        )

        await middleware(scope, _receive, collector.send)

        assert collector.status() == 204

    async def test_no_origin_header_passes_through_without_cors(self) -> None:
        config = CORSConfig(allowed_origins=["https://example.com"])
        middleware = CORSMiddleware(_bare_asgi_app, config)
        collector = _Collector()
        scope = _make_scope()  # no origin header

        await middleware(scope, _receive, collector.send)

        assert collector.status() == 200
        assert "Access-Control-Allow-Origin" not in collector.response_headers()

    async def test_non_http_scope_passes_through(self) -> None:
        config = CORSConfig(allowed_origins=["*"])
        messages: list[dict[str, Any]] = []

        async def noop_app(
            scope: dict[str, Any],
            receive: Callable[[], Awaitable[dict[str, Any]]],
            send: Callable[[dict[str, Any]], Awaitable[None]],
        ) -> None:
            messages.append(scope)

        middleware = CORSMiddleware(noop_app, config)
        await middleware({"type": "lifespan"}, _receive, _Collector().send)

        assert messages[0]["type"] == "lifespan"


# ---------------------------------------------------------------------------
# CSRFProtectionMiddleware (ASGI)
# ---------------------------------------------------------------------------


class TestCSRFMiddlewareIntegration:
    """Integration tests for CSRFProtectionMiddleware ASGI implementation."""

    async def test_get_request_passes_through_without_token(self) -> None:
        config = CSRFConfig(enabled=False)
        middleware = CSRFProtectionMiddleware(_bare_asgi_app, config)
        collector = _Collector()
        scope = _make_scope(method="GET")

        await middleware(scope, _receive, collector.send)

        assert collector.status() == 200

    async def test_post_without_token_returns_403(self) -> None:
        config = CSRFConfig(enabled=False)
        middleware = CSRFProtectionMiddleware(_bare_asgi_app, config)
        collector = _Collector()
        scope = _make_scope(method="POST")

        await middleware(scope, _receive, collector.send)

        assert collector.status() == 403

    async def test_put_without_token_returns_403(self) -> None:
        config = CSRFConfig(enabled=False)
        middleware = CSRFProtectionMiddleware(_bare_asgi_app, config)
        collector = _Collector()
        scope = _make_scope(method="PUT")

        await middleware(scope, _receive, collector.send)

        assert collector.status() == 403

    async def test_delete_without_token_returns_403(self) -> None:
        config = CSRFConfig(enabled=False)
        middleware = CSRFProtectionMiddleware(_bare_asgi_app, config)
        collector = _Collector()
        scope = _make_scope(method="DELETE")

        await middleware(scope, _receive, collector.send)

        assert collector.status() == 403

    async def test_non_http_scope_passes_through(self) -> None:
        config = CSRFConfig(enabled=False)
        messages: list[dict[str, Any]] = []

        async def noop_app(
            scope: dict[str, Any],
            receive: Callable[[], Awaitable[dict[str, Any]]],
            send: Callable[[dict[str, Any]], Awaitable[None]],
        ) -> None:
            messages.append(scope)

        middleware = CSRFProtectionMiddleware(noop_app, config)
        await middleware({"type": "lifespan"}, _receive, _Collector().send)

        assert messages[0]["type"] == "lifespan"


# ---------------------------------------------------------------------------
# GuardChain (core — unchanged import path)
# ---------------------------------------------------------------------------


class TestGuardChainIntegration:
    """Integration tests for GuardChain."""

    async def test_empty_chain_allows_everything(self) -> None:
        chain = GuardChain()
        result = await chain.check({})
        assert result is True

    async def test_allow_guard_passes(self) -> None:
        chain = GuardChain().add(_AllowGuard())
        result = await chain.check({"user_id": "u1"})
        assert result is True

    async def test_deny_guard_returns_false(self) -> None:
        chain = GuardChain().add(_DenyGuard())
        result = await chain.check({"user_id": "u1"})
        assert result is False

    async def test_mixed_chain_short_circuits_on_deny(self) -> None:
        chain = GuardChain().add(_AllowGuard()).add(_DenyGuard()).add(_AllowGuard())
        result = await chain.check({})
        assert result is False

    async def test_check_or_raise_passes_when_allowed(self) -> None:
        chain = GuardChain().add(_AllowGuard())
        await chain.check_or_raise({})  # must not raise

    async def test_check_or_raise_raises_guard_error_on_deny(self) -> None:
        chain = GuardChain().add(_DenyGuard())
        with pytest.raises(MiddlewareGuardError):
            await chain.check_or_raise({}, "Access denied")

    async def test_add_is_immutable(self) -> None:
        original = GuardChain()
        extended = original.add(_AllowGuard())
        assert original is not extended
        assert len(original._guards) == 0
        assert len(extended._guards) == 1


# ---------------------------------------------------------------------------
# Stacked middleware (end-to-end composition)
# ---------------------------------------------------------------------------


class TestStackedMiddleware:
    """Integration tests for composed middleware stacks."""

    async def test_cors_wrapping_csrf_passes_get_with_cors_headers(self) -> None:
        csrf = CSRFProtectionMiddleware(_bare_asgi_app, CSRFConfig(enabled=False))
        cors = CORSMiddleware(csrf, CORSConfig(allowed_origins=["https://example.com"]))
        collector = _Collector()
        scope = _make_scope(
            method="GET",
            headers=[(b"origin", b"https://example.com")],
        )

        await cors(scope, _receive, collector.send)

        assert collector.status() == 200
        assert "Access-Control-Allow-Origin" in collector.response_headers()

    async def test_cors_wrapping_csrf_blocks_post_without_csrf_token(self) -> None:
        csrf = CSRFProtectionMiddleware(_bare_asgi_app, CSRFConfig(enabled=False))
        cors = CORSMiddleware(csrf, CORSConfig(allowed_origins=["*"]))
        collector = _Collector()
        scope = _make_scope(
            method="POST",
            headers=[(b"origin", b"https://example.com")],
        )

        await cors(scope, _receive, collector.send)

        assert collector.status() == 403

    async def test_blocked_origin_still_enforces_csrf_block(self) -> None:
        csrf = CSRFProtectionMiddleware(_bare_asgi_app, CSRFConfig(enabled=False))
        cors = CORSMiddleware(csrf, CORSConfig(allowed_origins=["https://trusted.com"]))
        collector = _Collector()
        scope = _make_scope(
            method="POST",
            headers=[(b"origin", b"https://blocked.com")],
        )

        await cors(scope, _receive, collector.send)

        # CSRF middleware is inner layer; still returns 403 for POST without token
        assert collector.status() == 403
        # No CORS headers for blocked origin
        assert "Access-Control-Allow-Origin" not in collector.response_headers()
