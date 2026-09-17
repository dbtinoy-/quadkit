"""Cache-backed synchronizer token tests."""

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


from .csrf_test_support import (
    _cookie_header,
    _make_app,
    _make_scope,
    _responding_app,
    _run,
    _signed_cookie_pairs,
)


class _FakeCache:
    """In-memory CacheBackendProtocol stand-in for synchronizer-mode tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> Ok:
        return Ok(self.store.get(key))

    async def set(self, key: str, value: str, ttl: int | None = None) -> Ok:
        self.store[key] = value
        return Ok(None)

    async def delete(self, key: str) -> Ok:
        self.store.pop(key, None)
        return Ok(True)


@pytest.mark.asyncio
async def test_synchronizer_get_issues_cache_backed_token() -> None:
    """Safe method in synchronizer mode stores a server-side token."""
    config = CSRFConfig(cookie_name="csrf_token", header_name="X-CSRF-Token")
    cache = _FakeCache()
    middleware = CSRFProtectionMiddleware(_responding_app, config=config, cache=cache)

    scope = _make_scope(method="GET")
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    headers = dict(start.get("headers", []))
    cookie = headers.get(b"set-cookie", b"").decode()
    assert cookie.startswith("csrf_token=")
    ref = cookie.split("=", 1)[1].split(";", 1)[0]
    stored = cache.store.get(f"csrf:sync:{ref}")
    assert stored is not None, "synchronizer token must be stored in cache"
    assert headers.get(b"x-csrf-token", b"").decode() == stored


@pytest.mark.asyncio
async def test_synchronizer_post_matching_token_passes() -> None:
    """POST passing the cache-issued token through the header passes."""
    config = CSRFConfig(cookie_name="csrf_token", header_name="X-CSRF-Token")
    cache = _FakeCache()
    cache.store["csrf:sync:sync-ref-1"] = "server-issued-token"

    inner_called: list[bool] = []
    app = _make_app(called=inner_called)
    middleware = CSRFProtectionMiddleware(app, config=config, cache=cache)

    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": "sync-ref-1"}),
            (b"x-csrf-token", b"server-issued-token"),
        ],
    )
    await _run(middleware, scope)
    assert inner_called


@pytest.mark.asyncio
async def test_synchronizer_post_mismatch_rejected() -> None:
    """POST with a header token differing from the cached one is rejected."""
    config = CSRFConfig(cookie_name="csrf_token", header_name="X-CSRF-Token")
    cache = _FakeCache()
    cache.store["csrf:sync:sync-ref-2"] = "server-issued-token"
    app = _make_app()
    middleware = CSRFProtectionMiddleware(app, config=config, cache=cache)

    scope = _make_scope(
        method="POST",
        headers=[
            _cookie_header({"csrf_token": "sync-ref-2"}),
            (b"x-csrf-token", b"forged-header-token"),
        ],
    )
    messages = await _run(middleware, scope)
    start = next(m for m in messages if m.get("type") == "http.response.start")
    assert start["status"] == 403
