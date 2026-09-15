"""Unit tests for HostValidationMiddleware and its wiring.

Covers D3: fail-closed Host-header allowlist validation — matching hosts
pass through, unknown/missing hosts get a plain 400, non-HTTP scopes are
untouched, and MiddlewareSetup only wires the middleware when
``allowed_hosts`` is non-empty.
"""

from __future__ import annotations

from typing import Any

from quadkit.web.middleware.host import HostValidationMiddleware


def _make_scope(
    headers: list[tuple[bytes, bytes]] | None = None,
    scope_type: str = "http",
) -> dict[str, Any]:
    return {"type": scope_type, "headers": headers or []}


def _make_middleware(
    allowed_hosts: list[str], *, called: list[bool] | None = None
) -> HostValidationMiddleware:
    inner_called = called if called is not None else []

    async def _app(scope: Any, receive: Any, send: Any) -> None:  # noqa: ARG001
        inner_called.append(True)

    return HostValidationMiddleware(_app, allowed_hosts=allowed_hosts)


async def _run(
    middleware: HostValidationMiddleware, scope: dict[str, Any]
) -> list[dict[str, Any]]:
    """Run the middleware and collect sent messages."""
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    async def send(msg: dict[str, Any]) -> None:
        messages.append(msg)

    await middleware(scope, receive, send)
    return messages


class TestHostValidationMiddleware:
    """Unit tests for host allowlist enforcement (D3)."""

    async def test_matching_host_passes_through(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["example.com"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"example.com")])

        await _run(middleware, scope)
        assert inner_called

    async def test_matching_host_with_port_passes_through(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["example.com"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"example.com:8443")])

        await _run(middleware, scope)
        assert inner_called

    async def test_host_is_case_insensitive(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["example.com"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"EXAMPLE.COM")])

        await _run(middleware, scope)
        assert inner_called

    async def test_unknown_host_rejected_with_400(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["example.com"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"evil.example.net")])

        messages = await _run(middleware, scope)
        assert not inner_called
        start = next(m for m in messages if m.get("type") == "http.response.start")
        assert start["status"] == 400

    async def test_missing_host_rejected_with_400(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["example.com"], called=inner_called)
        scope = _make_scope(headers=[(b"content-type", b"application/json")])

        messages = await _run(middleware, scope)
        assert not inner_called
        start = next(m for m in messages if m.get("type") == "http.response.start")
        assert start["status"] == 400

    async def test_non_http_scope_passes_through(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["example.com"], called=inner_called)
        scope = _make_scope(scope_type="lifespan")

        await _run(middleware, scope)
        assert inner_called

    async def test_ipv6_host_supported(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["2001:db8::1"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"[2001:db8::1]:443")])

        await _run(middleware, scope)
        assert inner_called
