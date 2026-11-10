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

    async def test_leading_dot_matches_domain_and_subdomains(self) -> None:
        """``.example.com`` covers the apex and every subdomain (Django form)."""
        for host in ("example.com", "api.example.com", "a.b.example.com"):
            inner_called: list[bool] = []
            middleware = _make_middleware([".example.com"], called=inner_called)
            scope = _make_scope(headers=[(b"host", host.encode())])

            await _run(middleware, scope)
            assert inner_called, host

    async def test_wildcard_requires_a_subdomain(self) -> None:
        """``*.example.com`` matches subdomains but not the apex itself."""
        inner_called: list[bool] = []
        middleware = _make_middleware(["*.example.com"], called=inner_called)
        await _run(middleware, _make_scope(headers=[(b"host", b"example.com")]))
        assert not inner_called

        sub_called: list[bool] = []
        sub_middleware = _make_middleware(["*.example.com"], called=sub_called)
        await _run(sub_middleware, _make_scope(headers=[(b"host", b"api.example.com")]))
        assert sub_called

    async def test_suffix_match_respects_label_boundary(self) -> None:
        """A suffix entry must not accept a lookalike domain."""
        inner_called: list[bool] = []
        middleware = _make_middleware([".example.com"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"evilexample.com")])

        messages = await _run(middleware, scope)
        assert not inner_called
        assert messages[0]["status"] == 400

    async def test_suffix_match_is_case_insensitive_and_port_stripped(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware([".Example.COM"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"API.EXAMPLE.com:8443")])

        await _run(middleware, scope)
        assert inner_called

    async def test_preview_style_rotating_hosts_accepted(self) -> None:
        """Sandbox/preview hosts rotate per session — one suffix entry covers all."""
        middleware = _make_middleware([".e2b.app"])
        for port in (3000, 51742, 58080):
            inner_called: list[bool] = []
            middleware = _make_middleware([".e2b.app"], called=inner_called)
            scope = _make_scope(
                headers=[(b"host", f"{port}-i4p6e95b427s7lzhd7tuv.e2b.app".encode())]
            )

            await _run(middleware, scope)
            assert inner_called, port

    def test_bare_wildcard_is_refused(self) -> None:
        """An allow-anything entry would defeat the validator — fail at wiring."""
        import pytest

        with pytest.raises(ValueError, match="accept every Host"):
            _make_middleware(["*"])

    def test_empty_suffix_is_refused(self) -> None:
        import pytest

        for entry in (".", "*."):
            with pytest.raises(ValueError, match="empty domain suffix"):
                _make_middleware([entry])

    async def test_ipv6_host_supported(self) -> None:
        inner_called: list[bool] = []
        middleware = _make_middleware(["2001:db8::1"], called=inner_called)
        scope = _make_scope(headers=[(b"host", b"[2001:db8::1]:443")])

        await _run(middleware, scope)
        assert inner_called
