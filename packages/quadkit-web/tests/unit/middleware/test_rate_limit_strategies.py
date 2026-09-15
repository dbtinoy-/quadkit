"""Tests for rate-limit strategies: memory sliding window, cache fixed window, token bucket facade."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.result import Err, Ok
from quadkit.contracts.exceptions import RateLimitError
from quadkit.web.middleware.rate_limit_strategies import (
    CacheBackendLimiter,
    MemoryLimiter,
    RateLimiter,
)


class TestMemoryLimiter:
    async def test_allows_up_to_max(self) -> None:
        lim = MemoryLimiter(window_size=60, max_requests=2)
        assert await lim.try_acquire() is True
        assert await lim.try_acquire() is True
        assert await lim.try_acquire() is False

    async def test_current_requests(self) -> None:
        lim = MemoryLimiter(window_size=60, max_requests=5)
        assert lim.current_requests == 0
        await lim.try_acquire()
        await lim.try_acquire()
        assert lim.current_requests == 2

    async def test_window_expiry_releases_slots(self, monkeypatch) -> None:
        import quadkit.primitives.clock as clock_mod

        fake = {"t": 1000.0}

        class _FakeClock:
            def monotonic(self) -> float:
                return fake["t"]

        clock_mod._ambient.set(_FakeClock())  # noqa: SLF001

        lim = MemoryLimiter(window_size=10, max_requests=1)
        assert await lim.try_acquire() is True
        assert await lim.try_acquire() is False
        fake["t"] += 11  # window slid past
        assert await lim.try_acquire() is True

    async def test_partial_window_keeps_recent(self, monkeypatch) -> None:
        import quadkit.primitives.clock as clock_mod

        fake = {"t": 1000.0}

        class _FakeClock:
            def monotonic(self) -> float:
                return fake["t"]

        clock_mod._ambient.set(_FakeClock())  # noqa: SLF001

        lim = MemoryLimiter(window_size=10, max_requests=2)
        assert await lim.try_acquire() is True
        fake["t"] += 5
        assert await lim.try_acquire() is True
        assert lim.current_requests == 2
        fake["t"] += 5.1  # first request (t=1000) now outside window
        assert lim.current_requests == 1
        assert await lim.try_acquire() is True  # room for one more


class _FakeCache:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    async def get(self, key: str) -> object:
        if key in self.store:
            return Ok(self.store[key])
        return Err("miss")

    async def set(self, key: str, value: int, ttl: int | None = None) -> None:
        self.store[key] = value


class TestCacheBackendLimiter:
    async def test_allows_until_max(self) -> None:
        cache = _FakeCache()
        lim = CacheBackendLimiter(cache, window_size=60, max_requests=3)
        assert await lim.try_acquire("k") == (True, 2)
        assert await lim.try_acquire("k") == (True, 1)
        assert await lim.try_acquire("k") == (True, 0)
        assert await lim.try_acquire("k") == (False, 0)

    async def test_buckets_are_separate(self) -> None:
        cache = _FakeCache()
        lim = CacheBackendLimiter(cache, window_size=60, max_requests=1)
        assert await lim.try_acquire("a") == (True, 0)
        assert await lim.try_acquire("b") == (True, 0)
        assert await lim.try_acquire("a") == (False, 0)

    async def test_cache_key_shape(self) -> None:
        cache = _FakeCache()
        lim = CacheBackendLimiter(cache, window_size=60, max_requests=1)
        await lim.try_acquire("user:7")
        keys = list(cache.store)
        assert len(keys) == 1
        assert keys[0].startswith("rl:user:7:")
        assert cache.store[keys[0]] == 1

    async def test_get_error_treated_as_zero(self) -> None:
        cache = _FakeCache()
        lim = CacheBackendLimiter(cache, window_size=60, max_requests=1)
        # simulate cache errors (Err) for all reads: count degrades to 0
        cache.get = _always_err  # type: ignore[method-assign]
        assert await lim.try_acquire("k") == (True, 0)
        # persistent read errors mean the counter never accumulates
        assert await lim.try_acquire("k") == (True, 0)


async def _always_err(key: str) -> object:
    return Err("down")


def _request(host: str = "1.2.3.4", path: str = "/api", method: str = "GET", user_id: str | None = None, headers: dict | None = None):
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "query_string": b"",
        "client": (host, 12345),
    }
    request = Request(scope)
    if user_id is not None:
        request.state.user_id = user_id
    return request


class _FakeRedis:
    def __init__(self, responses: list[list[int]] | None = None) -> None:
        self.responses = responses or [[1, 5]]
        self.calls: list[tuple] = []
        self._i = 0

    async def eval(self, script: str, numkeys: int, key: str, *args) -> list[int]:
        self.calls.append((script, numkeys, key, args))
        resp = self.responses[min(self._i, len(self.responses) - 1)]
        self._i += 1
        return resp


class TestRateLimiterFacade:
    @pytest.fixture(autouse=True)
    def _stable_clock(self, monkeypatch) -> None:
        """Pin the wall clock so fixed-window buckets never roll over mid-test."""
        from datetime import UTC, datetime

        import quadkit.primitives.clock as clock_mod

        monkeypatch.setattr(
            clock_mod, "now", lambda: datetime.fromtimestamp(1_200_000.0, UTC)
        )
        monkeypatch.setattr(clock_mod, "timestamp", lambda: 1_200_000.0)

    async def test_memory_path_sets_state(self) -> None:
        limiter = RateLimiter()
        request = _request()
        await limiter.check_rate_limit(request, max_requests=5, window_seconds=60)
        assert request.state.rate_limit_remaining == 4
        assert request.state.rate_limit_limit == 5
        assert request.state.rate_limit_reset > 0

    async def test_memory_path_raises_when_exceeded(self) -> None:
        limiter = RateLimiter()
        for _ in range(2):
            await limiter.check_rate_limit(_request(), max_requests=2, window_seconds=60)
        with pytest.raises(RateLimitError) as exc_info:
            await limiter.check_rate_limit(_request(), max_requests=2, window_seconds=60)
        assert exc_info.value.details["retry_after"] == 60

    async def test_redis_path(self) -> None:
        redis = _FakeRedis(responses=[[1, 7], [0, 12]])
        limiter = RateLimiter(redis_client=redis)
        request = _request()
        await limiter.check_rate_limit(request, max_requests=10, window_seconds=60)
        assert request.state.rate_limit_remaining == 7
        # now the redis says denied
        with pytest.raises(RateLimitError) as exc_info:
            await limiter.check_rate_limit(_request(), max_requests=10, window_seconds=60)
        assert exc_info.value.details["retry_after"] == 12
        assert len(redis.calls) == 2
        script, numkeys, key, args = redis.calls[0]
        assert "ZREMRANGEBYSCORE" in script
        assert "ZADD" in script
        assert numkeys == 1
        assert key == "rate_limit:ip:1.2.3.4"
        assert args[2] == 10
        assert args[3] == 60

    async def test_cache_backend_path(self) -> None:
        cache = _FakeCache()
        limiter = RateLimiter(cache_backend=cache)
        request = _request()
        await limiter.check_rate_limit(request, max_requests=3, window_seconds=60)
        assert request.state.rate_limit_remaining == 2
        request2 = _request()
        await limiter.check_rate_limit(request2, max_requests=3, window_seconds=60)
        assert request2.state.rate_limit_remaining == 1
        request3 = _request()
        await limiter.check_rate_limit(request3, max_requests=3, window_seconds=60)
        assert request3.state.rate_limit_remaining == 0
        # fourth request in a max-3 window is denied
        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(_request(), max_requests=3, window_seconds=60)

    async def test_limiter_reuse_across_calls(self) -> None:
        limiter = RateLimiter()
        await limiter.check_rate_limit(_request(), max_requests=10, window_seconds=60)
        await limiter.check_rate_limit(_request(), max_requests=10, window_seconds=60)
        # same limiter instance reused (key includes max_requests + window)
        assert len(limiter._memory_limiters) == 1  # noqa: SLF001

    async def test_no_backend_warns_but_works(self) -> None:
        limiter = RateLimiter()  # logs a warning in __init__
        await limiter.check_rate_limit(_request(), max_requests=1, window_seconds=60)
        with pytest.raises(RateLimitError):
            await limiter.check_rate_limit(_request(), max_requests=1, window_seconds=60)


class TestScopeKeys:
    def test_user_scope_with_user(self) -> None:
        limiter = RateLimiter()
        request = _request(user_id="u-9")
        assert limiter._get_rate_limit_key(request, "user") == "user:u-9"  # noqa: SLF001

    def test_user_scope_falls_back_to_ip(self) -> None:
        limiter = RateLimiter()
        request = _request(host="9.9.9.9")
        assert limiter._get_rate_limit_key(request, "user") == "ip:9.9.9.9"  # noqa: SLF001

    def test_ip_scope(self) -> None:
        limiter = RateLimiter()
        request = _request(host="5.5.5.5")
        assert limiter._get_rate_limit_key(request, "ip") == "ip:5.5.5.5"  # noqa: SLF001

    def test_endpoint_scope(self) -> None:
        limiter = RateLimiter()
        request = _request(path="/api/things", method="POST")
        assert limiter._get_rate_limit_key(request, "endpoint") == "endpoint:POST:/api/things"  # noqa: SLF001

    def test_invalid_scope_raises(self) -> None:
        limiter = RateLimiter()
        with pytest.raises(ValueError, match="bogus"):
            limiter._get_rate_limit_key(_request(), "bogus")  # type: ignore[arg-type]


class TestClientIpTrustedProxies:
    def test_no_trusted_proxies_ignores_header(self) -> None:
        limiter = RateLimiter()
        request = _request(host="10.0.0.2", headers={"X-Forwarded-For": "8.8.8.8"})
        assert limiter._get_client_ip(request) == "10.0.0.2"  # noqa: SLF001

    def test_untrusted_peer_ignores_header(self) -> None:
        limiter = RateLimiter(trusted_proxies=frozenset({"10.0.0.1"}))
        request = _request(host="10.0.0.2", headers={"X-Forwarded-For": "8.8.8.8"})
        assert limiter._get_client_ip(request) == "10.0.0.2"  # noqa: SLF001

    def test_trusted_peer_honours_header(self) -> None:
        limiter = RateLimiter(trusted_proxies=frozenset({"10.0.0.1"}))
        request = _request(
            host="10.0.0.1", headers={"X-Forwarded-For": "8.8.8.8, 10.0.0.1"}
        )
        assert limiter._get_client_ip(request) == "8.8.8.8"  # noqa: SLF001

    def test_no_client_address(self) -> None:
        limiter = RateLimiter()
        from starlette.requests import Request

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/x",
            "root_path": "",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        assert limiter._get_client_ip(request) == "unknown"  # noqa: SLF001

    def test_trusted_peer_no_header(self) -> None:
        limiter = RateLimiter(trusted_proxies=frozenset({"10.0.0.1"}))
        request = _request(host="10.0.0.1")
        assert limiter._get_client_ip(request) == "10.0.0.1"  # noqa: SLF001
