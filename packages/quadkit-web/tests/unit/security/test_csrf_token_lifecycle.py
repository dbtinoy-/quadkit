"""CSRF cookie issuance, signing, staleness, tamper, and rotation tests."""

from __future__ import annotations

import time
from typing import Any

import pytest

from quadkit.web.security.config import CSRFConfig
from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

#: Any placeholder token value (unverifiable without a signing secret).
_RAW_TOKEN = "test-token-abc123"

#: Shared signing secret for verifiable-token tests.
_TEST_SECRET = "test-secret-key-32-bytes-long!!"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


from .csrf_test_support import (
    _cookie_header,
    _make_app,
    _make_scope,
    _responding_app,
    _run,
    _signed_cookie_pairs,
)


async def test_get_without_csrf_cookie_sets_cookie() -> None:
    config = CSRFConfig(cookie_name="csrf_token")

    # App must actually send a response so the CSRF cookie injection fires
    async def _responding_app(scope: Any, receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = CSRFProtectionMiddleware(_responding_app, config=config)

    scope = _make_scope(method="GET")
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    headers_list = start.get("headers", [])
    header_names = {name for name, _ in headers_list}
    # Should have set a CSRF cookie
    assert b"set-cookie" in header_names, "GET without cookie should set a CSRF cookie"


# ---------------------------------------------------------------------------
# Double-submit cookie validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_with_matching_signed_tokens_passes() -> None:
    """POST with a valid signed cookie and the matching header passes."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
    )
    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app, config=config)

    token = middleware._build_signed_token(int(time.time()))
    assert token is not None
    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": token}),
            (b"x-csrf-token", token.encode()),
        ],
    )
    await _run(middleware, scope)
    assert inner_called, "POST with matching signed CSRF cookie and header should pass"


@pytest.mark.asyncio
async def test_post_without_secret_fails_closed() -> None:
    """Without a signing secret even matching raw tokens are rejected."""
    config = CSRFConfig(cookie_name="csrf_token", header_name="X-CSRF-Token")
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": _RAW_TOKEN}),
            (b"x-csrf-token", _RAW_TOKEN.encode()),
        ],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


@pytest.mark.asyncio
async def test_post_with_stale_signed_token_rejected() -> None:
    """Expired signed tokens are rejected on unsafe methods."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
        token_ttl=600,
    )
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    stale_ts = int(time.time()) - 601
    token = middleware._build_signed_token(stale_ts)
    assert token is not None
    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": token}),
            (b"x-csrf-token", token.encode()),
        ],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


@pytest.mark.asyncio
async def test_post_with_tampered_signature_rejected() -> None:
    """A valid payload with a forged signature is rejected."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
    )
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    token = middleware._build_signed_token(int(time.time()))
    assert token is not None
    payload, _sig = token.rsplit(".", 1)
    # Mutate a middle signature character: the final char of an unpadded
    # 32-byte base64url signature carries only 4 meaningful bits, so
    # replacing it can decode to the identical digest (1/16 of the time)
    # and let a "forged" token pass verification. A middle char always
    # changes the decoded signature bytes.
    alt = "B" if _sig[10] != "B" else "C"
    forged = f"{payload}.{_sig[:10]}{alt}{_sig[11:]}"
    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": forged}),
            (b"x-csrf-token", forged.encode()),
        ],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


@pytest.mark.asyncio
async def test_post_with_unparseable_token_rejected() -> None:
    """Malformed token shapes (no signature) are rejected."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
    )
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": _RAW_TOKEN}),
            (b"x-csrf-token", _RAW_TOKEN.encode()),
        ],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


@pytest.mark.asyncio
async def test_post_with_mismatched_tokens_returns_403() -> None:
    """A valid cookie with a different header value is rejected."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
    )
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    token = middleware._build_signed_token(int(time.time()))
    assert token is not None
    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": token}),
            (b"x-csrf-token", b"different-header-token"),
        ],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


# ---------------------------------------------------------------------------
# Signed token issuance & rotation (cookie mode)
# ---------------------------------------------------------------------------




async def test_get_without_cookie_sets_cookie() -> None:
    """GET without a CSRF cookie issues one (random fallback without a secret)."""
    config = CSRFConfig(cookie_name="csrf_token")
    middleware = CSRFProtectionMiddleware(_responding_app, config=config)

    scope = _make_scope(method="GET")
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    header_names = {name for name, _ in start.get("headers", [])}
    assert b"set-cookie" in header_names, "GET without cookie should set a CSRF cookie"


@pytest.mark.asyncio
async def test_get_with_secret_sets_signed_token() -> None:
    """With a secret, a fresh signed token is issued and exposed in the header."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
    )
    middleware = CSRFProtectionMiddleware(_responding_app, config=config)

    scope = _make_scope(method="GET")
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    headers = dict(start.get("headers", []))
    cookie = headers.get(b"set-cookie", b"").decode()
    assert cookie.startswith("csrf_token=")
    issued = cookie.split("=", 1)[1].split(";", 1)[0]
    assert "." in issued, "issued token must be signed (payload.signature)"

    header_token = headers.get(b"x-csrf-token", b"").decode()
    assert header_token == issued, "SPA must be able to read the issued token"

    parsed = middleware._parse_token(issued)
    assert parsed is not None


@pytest.mark.asyncio
async def test_get_with_fresh_cookie_does_not_rotate() -> None:
    """A fresh valid cookie is reused — no Set-Cookie on the response."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
        token_ttl=3600,
    )
    middleware = CSRFProtectionMiddleware(_responding_app, config=config)
    token = middleware._build_signed_token(int(time.time()))
    assert token is not None

    scope = _make_scope(
        method="GET",
        headers=[_cookie_header({"csrf_token": token})],
    )
    messages = await _run(middleware, scope)
    pairs = _signed_cookie_pairs(messages)
    assert "set-cookie" not in pairs, "fresh token must not be rotated"
    start = next(m for m in messages if m.get("type") == "http.response.start")
    headers = dict(start.get("headers", []))
    assert headers.get(b"x-csrf-token", b"").decode() == token


@pytest.mark.asyncio
async def test_get_with_stale_cookie_rotates_token() -> None:
    """A stale signed cookie is rotated on the next safe method."""
    config = CSRFConfig(
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
        secret_key=_TEST_SECRET,
        token_ttl=600,
    )
    middleware = CSRFProtectionMiddleware(_responding_app, config=config)
    stale_ts = int(time.time()) - 601
    stale = middleware._build_signed_token(stale_ts)
    assert stale is not None

    scope = _make_scope(
        method="GET",
        headers=[_cookie_header({"csrf_token": stale})],
    )
    messages = await _run(middleware, scope)
    pairs = _signed_cookie_pairs(messages)
    assert "set-cookie" in pairs, "stale token must be rotated"
    rotated = pairs["set-cookie"].split("=", 1)[1].split(";", 1)[0]
    assert rotated != stale
    assert middleware._parse_token(rotated) is not None


# ---------------------------------------------------------------------------
# Synchronizer token mode (cache-backed)
# ---------------------------------------------------------------------------


