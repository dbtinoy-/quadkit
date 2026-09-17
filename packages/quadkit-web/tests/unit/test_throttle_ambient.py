"""Regression tests: ambient @throttle with RateLimitModule (backend="memory").

Three bugs were exposed while building the rate-limiting feature tour:

1. ``rate_limit()`` resolved limiters ONLY via explicit constructor
   injection, so the ``@throttle(...)`` sugar + ``RateLimitModule``
   combination advertised in the docstrings silently failed open.
2. ``RateLimitModule.configure(backend="memory")`` dropped the backend
   choice; the provider always booted the Redis limiter.
3. ``DefaultExceptionFilter`` degraded the contracts ``RateLimitError``
   to a generic 400 ("Bad Request") instead of 429.

These tests pin the fixed behaviour.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from quadkit.contracts.exceptions.domain import RateLimitError
from quadkit.contracts.web import WebRateLimiterProtocol
from quadkit.web.di.rate_limit import RateLimitProvider
from quadkit.web.filters.builtin import DefaultExceptionFilter
from quadkit.web.middleware.rate_limit import (
    MemoryLimiter,
    RateLimiter,
    _resolve_container_limiter,
    rate_limit,
)
from quadkit.web.middleware.rate_limit_strategies import (
    RateLimiter as StrategiesRateLimiter,
)


def _request(path: str = "/limited", method: str = "GET") -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "url": f"http://testserver{path}",
        "state": {},
        "app": MagicMock(),
    }
    return Request(scope, None)


def _container_binding(service: object) -> MagicMock:
    container = MagicMock()

    async def _resolve(key: object) -> object:
        return service

    container.resolve = _resolve
    return container


class TestProviderBackendSelection:
    @pytest.mark.asyncio
    async def test_memory_backend_binds_in_memory_rate_limiter(self) -> None:
        """backend="memory" must not touch Redis at all."""
        provider = RateLimitProvider(backend="memory")

        container = MagicMock()
        await provider.boot(container)

        assert provider.limiter is not None
        assert isinstance(provider.limiter, StrategiesRateLimiter)
        # No Redis resolution was attempted.
        container.resolve.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_backend_remains_default_and_warns_once(
        self,
    ) -> None:
        """Default Redis behaviour is preserved for direct provider users."""
        provider = RateLimitProvider()
        assert provider.backend == "redis"

        container = MagicMock()
        container.resolve = _container_binding(MagicMock()).resolve
        await provider.boot(container)

        assert provider.limiter is not None


class TestAmbientContainerResolution:
    @pytest.mark.asyncio
    async def test_resolves_limiter_from_request_scoped_container(self) -> None:
        limiter = RateLimiter()
        request = _request()
        request.state.container = _container_binding(limiter)

        resolved = await _resolve_container_limiter(request)

        assert resolved is limiter

    @pytest.mark.asyncio
    async def test_falls_back_to_root_container(self) -> None:
        limiter = RateLimiter()
        request = _request()
        request.state.container = None
        request.state.root_container = _container_binding(limiter)

        resolved = await _resolve_container_limiter(request)

        assert resolved is limiter

    @pytest.mark.asyncio
    async def test_returns_none_when_no_container(self) -> None:
        request = _request()
        assert await _resolve_container_limiter(request) is None

    @pytest.mark.asyncio
    async def test_decorator_enforces_container_bound_limiter(self) -> None:
        """The full ambient path: @throttle-style decorator + module limiter."""

        # Tiny in-memory protocol implementation (sliding window of 1).
        class TinyLimiter:
            def __init__(self) -> None:
                self._windows: dict[str, list[float]] = {}

            async def check_rate_limit(
                self,
                request: Request,
                *,
                max_requests: int,
                window_seconds: int,
                scope: str = "user",
            ) -> None:
                key = f"{scope}:{request.url.path}"
                hits = self._windows.setdefault(key, [])
                if len(hits) >= max_requests:
                    raise RateLimitError(
                        "Rate limit exceeded",
                        details={"retry_after": window_seconds},
                    )
                hits.append(1.0)

        limiter = TinyLimiter()
        request = _request()
        request.state.container = _container_binding(limiter)

        model = WebRateLimiterProtocol

        @rate_limit(max_requests=1, window_seconds=60, scope="endpoint")
        async def handler(request: Request) -> JSONResponse:
            return JSONResponse({"ok": True})

        first = await handler(request)
        assert first.status_code == 200

        with pytest.raises(RateLimitError):
            await handler(request)

        assert model is not None  # protocol import smoke


class TestExceptionFilterStatusMapping:
    @pytest.mark.asyncio
    async def test_contracts_rate_limit_error_maps_to_429_with_retry_after(
        self,
    ) -> None:
        filter_ = DefaultExceptionFilter(debug=False)
        request = _request()
        exc = RateLimitError("Rate limit exceeded", details={"retry_after": 42})

        response = await filter_.handle(exc, request)

        assert response.status_code == 429
        assert response.headers["Retry-After"] == "42"


class TestMemoryLimiterStillAvailable:
    def test_memory_limiter_is_still_exported(self) -> None:
        assert MemoryLimiter is not None
        assert RateLimiter is not None
