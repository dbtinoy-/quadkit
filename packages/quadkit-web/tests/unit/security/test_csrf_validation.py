"""CSRF request validation and exemption-path tests."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.result import Ok
from quadkit.web.security.config import CSRFConfig
from quadkit.web.security.csrf.middleware import CSRFProtectionMiddleware

#: Any placeholder token value (unverifiable without a signing secret).
_RAW_TOKEN = "test-token-abc123"

#: Shared signing secret for verifiable-token tests.
_TEST_SECRET = "test-secret-key-32-bytes-long!!"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


from csrf_test_support import _cookie_header, _make_app, _make_scope, _run


async def test_non_http_scope_passes_through() -> None:
    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app)
    scope = {"type": "websocket", "path": "/ws"}
    await _run(middleware, scope)
    assert inner_called


# ---------------------------------------------------------------------------
# Excluded paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excluded_path_skips_validation_on_post() -> None:
    config = CSRFConfig(excluded_paths=["/api/"])
    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(method="POST", path="/api/data")
    await _run(middleware, scope)
    assert inner_called, "Excluded path should bypass CSRF validation"


@pytest.mark.asyncio
async def test_non_excluded_post_without_token_returns_403() -> None:
    config = CSRFConfig(excluded_paths=["/api/"])
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(method="POST", path="/form")
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


# ---------------------------------------------------------------------------
# Cookie-aware excluded paths (F-W2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_excluded_path_with_cookie_still_validates() -> None:
    """Excluded-path bypass applies to cookie-less clients; cookie-bearing
    requests on excluded paths are validated."""
    config = CSRFConfig(
        excluded_paths=["/api/"],
        cookie_name="csrf_token",
        header_name="X-CSRF-Token",
    )
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="POST",
        path="/api/data",
        headers=[_cookie_header({"csrf_token": "tok"})],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


@pytest.mark.asyncio
async def test_excluded_path_with_cookie_and_matching_token_passes() -> None:
    """Cookie-bearing excluded-path requests pass when tokens match."""
    config = CSRFConfig(
        excluded_paths=["/api/"],
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
        path="/api/data",
        headers=[
            _cookie_header({"csrf_token": token}),
            (b"x-csrf-token", token.encode()),
        ],
    )
    await _run(middleware, scope)
    assert inner_called


@pytest.mark.asyncio
async def test_excluded_path_with_cookie_json_content_type_passes() -> None:
    """JSON clients keep their bypass on excluded paths even with cookies."""
    config = CSRFConfig(
        excluded_paths=["/api/"],
        exclude_content_types=["application/json"],
    )
    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="POST",
        path="/api/data",
        headers=[
            _cookie_header({"csrf_token": "tok"}),
            (b"content-type", b"application/json"),
        ],
    )
    await _run(middleware, scope)
    assert inner_called


@pytest.mark.asyncio
async def test_excluded_safe_method_with_cookie_passes() -> None:
    """Safe methods on excluded paths pass through regardless of cookies."""
    config = CSRFConfig(excluded_paths=["/api/"], cookie_name="csrf_token")
    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="GET",
        path="/api/data",
        headers=[_cookie_header({"csrf_token": "tok"})],
    )
    await _run(middleware, scope)
    assert inner_called


# ---------------------------------------------------------------------------
# Content-type exclusion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_content_type_skips_csrf_validation() -> None:
    config = CSRFConfig(exclude_content_types=["application/json"])
    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="POST",
        headers=[(b"content-type", b"application/json")],
    )
    await _run(middleware, scope)
    assert inner_called, "JSON requests should bypass CSRF validation"


@pytest.mark.asyncio
async def test_form_post_without_token_returns_403() -> None:
    config = CSRFConfig()
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="POST",
        headers=[(b"content-type", b"application/x-www-form-urlencoded")],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403


# ---------------------------------------------------------------------------
# Auth scheme exclusion
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bearer_auth_skips_csrf_validation() -> None:
    config = CSRFConfig(exclude_auth_schemes=["bearer"])
    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app, config=config)

    scope = _make_scope(
        method="POST",
        headers=[(b"authorization", b"Bearer token123")],
    )
    await _run(middleware, scope)
    assert inner_called, "Bearer auth requests should bypass CSRF validation"


# ---------------------------------------------------------------------------
# Safe methods issue token cookie
# ---------------------------------------------------------------------------


