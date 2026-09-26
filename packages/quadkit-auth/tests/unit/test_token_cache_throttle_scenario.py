"""Scenario tests for the token cache (L1/LRU/L2) and rate-limit throttle.

Hermetic: ``TokenCache`` is driven with a fixed ambient clock; the rate
limiter is driven with a fake monotonic clock injected via
``quadkit.primitives.clock`` so window expiry and block release are
deterministic (no wall-clock sleeps).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from quadkit import serialization as _json
from quadkit.result import Ok
from quadkit.testing.clock import FixedClock

from quadkit.auth.web.middleware.token_cache import TokenCache
from quadkit.auth.web.middleware.throttle import (
    RateLimitExceededError,
    RateLimitMiddleware,
    _parse_rate_limit,
    throttle,
)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# --------------------------------------------------------------------------
# TokenCache — L1 only
# --------------------------------------------------------------------------


async def test_token_cache_set_get_hit() -> None:
    cache = TokenCache()
    await cache.set("tok-1", "user-1")
    assert await cache.get("tok-1") == "user-1"
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 0
    assert stats["hit_rate_percent"] == 100.0
    assert stats["size"] == 1


async def test_token_cache_miss_and_stats() -> None:
    cache = TokenCache()
    assert await cache.get("absent") is None
    await cache.set("a", 1)
    assert await cache.get("absent") is None
    stats = cache.stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 2
    assert stats["hit_rate_percent"] == 0.0


async def test_token_cache_ttl_expiry() -> None:
    clock = FixedClock()
    from quadkit.primitives import clock as ambient

    with ambient.use(clock):
        cache = TokenCache(ttl_seconds=10.0)
        await cache.set("t", "u")
        assert await cache.get("t") == "u"

        clock.advance(11)
        assert await cache.get("t") is None
        assert cache.stats()["size"] == 0  # expired entry removed on get


async def test_token_cache_lru_eviction() -> None:
    cache = TokenCache(max_size=2, ttl_seconds=3600)
    await cache.set("t1", "u1")
    await cache.set("t2", "u2")
    # touch t1 so t2 becomes least recently used
    assert await cache.get("t1") == "u1"
    await cache.set("t3", "u3")  # evicts t2
    assert await cache.get("t2") is None
    assert await cache.get("t1") == "u1"
    assert await cache.get("t3") == "u3"
    assert cache.stats()["size"] == 2


async def test_token_cache_invalidate_and_clear() -> None:
    cache = TokenCache()
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.invalidate("a")
    assert await cache.get("a") is None
    assert await cache.get("b") == 2

    cache.clear()
    assert cache.stats()["size"] == 0
    assert cache.stats()["hits"] == 0
    assert cache.stats()["misses"] == 0


async def test_token_cache_invalidate_unknown_is_noop() -> None:
    cache = TokenCache()
    await cache.invalidate("never-seen")  # must not raise
    assert cache.stats()["size"] == 0


# --------------------------------------------------------------------------
# TokenCache — L2 backend integration
# --------------------------------------------------------------------------


class _FakeBackend:
    def __init__(self, fail_get: bool = False) -> None:
        self.store: dict[str, Any] = {}
        self.fail_get = fail_get
        self.set_calls: list[tuple[str, Any, int]] = []
        self.delete_calls: list[str] = []

    async def get(self, key: str) -> Any:
        if self.fail_get:
            from quadkit.result import Err

            return Err("backend down")
        return Ok(self.store.get(key))

    async def set(self, key: str, value: Any, ttl: int | None = None) -> Any:
        self.set_calls.append((key, value, ttl or 0))
        self.store[key] = value
        return Ok(None)

    async def delete(self, key: str) -> Any:
        self.delete_calls.append(key)
        self.store.pop(key, None)
        return Ok(True)


async def test_token_cache_l2_populates_and_serves() -> None:
    backend = _FakeBackend()
    cache = TokenCache(ttl_seconds=3600, cache_backend=backend)
    await cache.set("t", "user-x")

    # written to L2 under the hashed key with the ttl
    assert backend.store[f"token:{_token_hash('t')}"] == "user-x"
    assert backend.set_calls[0][2] == 3600

    # new L1 (same backend) serves from L2 and repopulates L1
    cache2 = TokenCache(ttl_seconds=3600, cache_backend=backend)
    assert await cache2.get("t") == "user-x"
    assert cache2.stats()["hits"] == 1
    # and L1 is now warm
    assert await cache2.get("t") == "user-x"


async def test_token_cache_l2_get_failure_degrades_to_miss() -> None:
    backend = _FakeBackend(fail_get=True)
    cache = TokenCache(cache_backend=backend)
    # Err result must not propagate — degrades to a plain miss
    assert await cache.get("t") is None
    assert cache.stats()["misses"] == 1


async def test_token_cache_invalidate_removes_from_backend() -> None:
    backend = _FakeBackend()
    cache = TokenCache(cache_backend=backend)
    await cache.set("t", "u")
    await cache.invalidate("t")
    assert f"token:{_token_hash('t')}" in backend.delete_calls
    assert f"token:{_token_hash('t')}" not in backend.store


# --------------------------------------------------------------------------
# Rate limiter
# --------------------------------------------------------------------------


def _parse_matrix() -> None:
    assert _parse_rate_limit("5/minute") == (5, 60)
    assert _parse_rate_limit("2/seconds") == (2, 1)
    assert _parse_rate_limit("3/hours") == (3, 3600)
    assert _parse_rate_limit(" 4 / Minute ") == (4, 60)
    with pytest.raises(ValueError, match="Invalid rate_limit"):
        _parse_rate_limit("nope")
    with pytest.raises(ValueError, match="Unknown period"):
        _parse_rate_limit("5/decade")


def _asgi_scope(path: str, client: tuple[str, int] | None = ("10.0.0.1", 5555)) -> dict[str, Any]:
    return {
        "type": "http",
        "path": path,
        "method": "POST",
        "client": client,
        "headers": [],
        "query_string": b"",
        "root_path": "",
    }


async def _drive(
    mw: RateLimitMiddleware,
    path: str = "/auth/login",
    client: tuple[str, int] | None = ("10.0.0.1", 5555),
    status: int = 200,
) -> list[int]:
    """Send one request through the middleware; return observed statuses."""
    statuses: list[int] = []
    app_called = {"v": False}

    async def app(scope: Any, receive: Any, send: Any) -> None:
        app_called["v"] = True
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    mw.app = app

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    messages: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await mw(_asgi_scope(path, client), receive, send)
    statuses.extend(m.get("status") for m in messages if m.get("type") == "http.response.start")
    return statuses


# The limiter accumulates **non-2xx** attempts (failed logins); a 2xx
# response clears the client's history. All block-scenarios below drive
# 401 responses to model brute-force accumulation.


async def test_rate_limiter_failure_accumulation_blocks() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="3/minute")
        for _ in range(3):
            assert await _drive(mw, status=401) == [401]
        assert "10.0.0.1" not in mw.blocked
        # 4th failing request within the window -> 429 + block
        assert await _drive(mw, status=401) == [429]
        assert "10.0.0.1" in mw.blocked


async def test_rate_limiter_block_and_release() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="2/minute", block_duration=30)
        assert await _drive(mw, status=401) == [401]
        assert await _drive(mw, status=401) == [401]
        assert await _drive(mw) == [429]  # blocked until t=30

        # still blocked partway through the block duration
        clock.advance(10)
        assert await _drive(mw) == [429]

        # block expired -> released; the two in-window failures (t=0,
        # 60s window) now re-trigger the limit immediately
        clock.advance(30)
        assert await _drive(mw) == [429]

        # after the failures slide out of the window the client is clean
        clock.advance(61)
        assert await _drive(mw, status=401) == [401]
        assert await _drive(mw, status=401) == [401]


async def test_rate_limiter_sliding_window_expiry() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="2/minute")
        assert await _drive(mw, status=401) == [401]
        assert await _drive(mw, status=401) == [401]
        # window still full
        assert await _drive(mw) == [429]

        # attempts slide out of the 60s window
        clock.advance(61)
        del mw.blocked["10.0.0.1"]  # block itself expires too
        assert await _drive(mw, status=401) == [401]


async def test_rate_limiter_success_clears_history() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="2/minute")
        assert await _drive(mw, status=401) == [401]
        # 2xx clears the attempt history — a legitimate user is never
        # carried over into a later window
        assert await _drive(mw, status=200) == [200]
        assert mw.attempts["10.0.0.1"] == []
        assert await _drive(mw, status=401) == [401]  # fresh window


async def test_rate_limiter_non_success_keeps_history() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="2/minute")
        assert await _drive(mw, status=401) == [401]
        assert await _drive(mw, status=500) == [500]
        assert await _drive(mw, status=401) == [429]  # both counted


async def test_rate_limiter_path_and_scope_gating() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="1/minute")
        # non-limited path always passes, even with failures
        for _ in range(5):
            assert await _drive(mw, path="/api/data", status=401) == [401]
        assert not mw.attempts

        # non-http scope passes through untouched
        app_called = {"v": False}

        async def app(scope: Any, receive: Any, send: Any) -> None:
            app_called["v"] = True
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        mw.app = app

        async def receive() -> dict[str, Any]:
            return {}

        async def send(message: Any) -> None:
            None

        await mw({"type": "websocket", "path": "/auth/login"}, receive, send)
        assert app_called["v"] is True


async def test_rate_limiter_client_isolation_and_unknown() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="1/minute")
        a = ("10.0.0.1", 1)
        b = ("10.0.0.2", 2)
        assert await _drive(mw, client=a, status=401) == [401]
        assert await _drive(mw, client=a) == [429]
        # different client unaffected
        assert await _drive(mw, client=b, status=401) == [401]
        # missing client -> bucket "unknown"
        assert await _drive(mw, client=None, status=401) == [401]
        assert await _drive(mw, client=None) == [429]


async def test_rate_limiter_429_body_and_headers() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        mw = RateLimitMiddleware(app=None, rate_limit="1/minute", block_duration=15)
        await _drive(mw, status=401)

        messages: list[dict[str, Any]] = []

        async def app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        mw.app = app

        async def receive() -> dict[str, Any]:
            return {}

        async def send(message: dict[str, Any]) -> None:
            messages.append(message)

        await mw(_asgi_scope("/auth/login"), receive, send)
        start = next(m for m in messages if m["type"] == "http.response.start")
        body = next(m for m in messages if m["type"] == "http.response.body")
        assert start["status"] == 429
        headers = dict(start["headers"])
        assert headers[b"retry-after"] == b"15"
        payload = _json.loads(body["body"])
        assert payload["retry_after"] == 15
        assert "detail" in payload


async def test_rate_limiter_custom_paths_and_factory() -> None:
    from quadkit.primitives import clock as ambient

    clock = FixedClock()
    with ambient.use(clock):
        paths = frozenset({"/custom/login"})
        mw = RateLimitMiddleware(app=None, rate_limit="1/minute", paths=paths)
        assert await _drive(mw, path="/custom/login", status=401) == [401]
        assert await _drive(mw, path="/custom/login") == [429]
        # built-in paths are NOT limited with a custom set
        assert await _drive(mw, path="/auth/login", status=401) == [401]

        # factory form
        async def base_app(scope: Any, receive: Any, send: Any) -> None:
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        wrapped = throttle(rate_limit="1/minute", paths=paths)(base_app)
        assert isinstance(wrapped, RateLimitMiddleware)
        assert wrapped._max_requests == 1  # noqa: SLF001


def test_rate_limit_exceeded_error() -> None:
    err = RateLimitExceededError(30)
    assert err.retry_after == 30
    assert "30" in str(err)
    assert err._code == "QK_ERR_SEC_012"  # noqa: SLF001
