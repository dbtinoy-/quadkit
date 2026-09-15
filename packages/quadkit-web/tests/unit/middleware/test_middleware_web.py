"""Unit tests for middleware domain"""

import asyncio
from unittest.mock import Mock

import pytest
import pytest_asyncio
from starlette.requests import Request

from quadkit.contracts.exceptions import RateLimitError
from quadkit.web.middleware.compression import CompressionMiddleware
from quadkit.web.middleware.cors import CORSMiddleware
from quadkit.web.middleware.rate_limit import (
    RateLimiter,
    RateLimitMiddleware,
)
from quadkit.web.middleware.timing import TimingMiddleware

# from quadkit.web import JSONResponse # This import is now shadowed by starlette.responses.JSONResponse, but it's not used in the new tests, so it can stay or be removed. I'll keep it as per instruction to not make unrelated edits.


class TestCORSMiddleware:
    """Test CORS middleware functionality"""

    @pytest.fixture
    def app(self):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def endpoint(request):
            return JSONResponse({"data": "test"})

        app = Starlette(
            routes=[Route("/", endpoint, methods=["GET", "POST", "OPTIONS"])]
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            allow_credentials=True,
        )
        return app

    @pytest.fixture
    def client(self, app):
        from starlette.testclient import TestClient

        return TestClient(app)

    def test_cors_middleware_creation(self):
        """Test CORS middleware instantiation"""
        mock_app = Mock()
        mw = CORSMiddleware(
            app=mock_app,
            allow_origins=["http://localhost:3000"],
            allow_methods=["GET", "POST"],
        )
        assert mw is not None
        assert mw.config.allow_origins == ["http://localhost:3000"]
        assert mw.config.allow_methods == ["GET", "POST"]

    def test_cors_preflight_request(self, client):
        """Test CORS preflight request handling"""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        assert response.status_code == 204
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )
        assert "POST" in response.headers.get("access-control-allow-methods", "")

    def test_cors_actual_request(self, client):
        """Test CORS headers on actual request"""
        response = client.get("/", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "http://localhost:3000"
        )


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest_asyncio.fixture
    async def limiter(self):
        """Create rate limiter using in-memory fallback (no Redis)."""
        # Use in-memory limiter by passing None for redis_client
        # This uses SlidingWindowLimiter internally which is easier to test
        return RateLimiter(redis_client=None)

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock()
        request.client = Mock()
        request.client.host = "192.168.1.100"
        request.state = Mock()
        request.state.user_id = "user_123"
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(
        self,
        limiter: RateLimiter,
        mock_request: Request,
    ) -> None:
        """Test that requests within limit are allowed."""
        # Act - make 5 requests (limit is 10)
        for i in range(5):
            await limiter.check_rate_limit(
                mock_request,
                max_requests=10,
                window_seconds=60,
            )

        # Assert - no exception raised

    @pytest.mark.asyncio
    async def test_blocks_requests_exceeding_limit(
        self,
        limiter: RateLimiter,
        mock_request: Request,
    ) -> None:
        """Test that requests exceeding limit are blocked."""
        # Arrange - exhaust limit
        for i in range(10):
            await limiter.check_rate_limit(
                mock_request,
                max_requests=10,
                window_seconds=60,
            )

        # Act & Assert - next request should be blocked
        with pytest.raises(RateLimitError) as exc_info:
            await limiter.check_rate_limit(
                mock_request,
                max_requests=10,
                window_seconds=60,
            )

        assert exc_info.value.details.get("retry_after", 0) > 0

    @pytest.mark.asyncio
    async def test_sliding_window_allows_requests_after_window(
        self,
        limiter: RateLimiter,
        mock_request: Request,
    ) -> None:
        """Test that requests are allowed after window expires."""
        # Arrange - exhaust limit with 1 second window
        for i in range(5):
            await limiter.check_rate_limit(
                mock_request,
                max_requests=5,
                window_seconds=1,
            )

        # Wait for window to expire
        await asyncio.sleep(1.1)

        # Act - should be allowed now
        await limiter.check_rate_limit(
            mock_request,
            max_requests=5,
            window_seconds=1,
        )

        # Assert - no exception raised

    @pytest.mark.asyncio
    async def test_different_users_have_separate_limits(
        self,
        limiter: RateLimiter,
        mock_request: Request,
    ) -> None:
        """Test that different users have independent limits."""
        # Arrange - exhaust limit for user 1
        mock_request.state.user_id = "user_1"
        for i in range(10):
            await limiter.check_rate_limit(
                mock_request,
                max_requests=10,
                window_seconds=60,
                scope="user",
            )

        # Act - user 2 should still be allowed
        mock_request.state.user_id = "user_2"
        await limiter.check_rate_limit(
            mock_request,
            max_requests=10,
            window_seconds=60,
            scope="user",
        )

        # Assert - no exception raised

    @pytest.mark.asyncio
    async def test_ip_fallback_when_no_user(
        self,
        limiter: RateLimiter,
        mock_request: Request,
    ) -> None:
        """Test that IP is used when no user ID."""
        # Arrange - remove user_id
        mock_request.state.user_id = None

        # Act - should use IP
        await limiter.check_rate_limit(
            mock_request,
            max_requests=10,
            window_seconds=60,
            scope="user",  # Should fall back to IP
        )

        # Assert - no exception raised

    @pytest.mark.asyncio
    async def test_per_endpoint_limits(
        self,
        limiter: RateLimiter,
        mock_request: Request,
    ) -> None:
        """Test per-endpoint rate limiting."""
        # Arrange - different endpoints
        mock_request.url.path = "/api/endpoint1"
        await limiter.check_rate_limit(
            mock_request,
            max_requests=5,
            window_seconds=60,
            scope="endpoint",
        )

        mock_request.url.path = "/api/endpoint2"
        # Should be allowed (different endpoint)
        await limiter.check_rate_limit(
            mock_request,
            max_requests=5,
            window_seconds=60,
            scope="endpoint",
        )

        # Assert - no exception raised

    @pytest.mark.asyncio
    async def test_x_forwarded_for_header(
        self,
        mock_request: Request,
    ) -> None:
        """X-Forwarded-For is honoured only when the direct peer is trusted."""
        # Arrange — limiter trusts the direct client IP.
        trusted_limiter = RateLimiter(
            redis_client=None,
            trusted_proxies=frozenset({"192.168.1.100"}),
        )
        mock_request.headers["X-Forwarded-For"] = "10.0.0.1, 192.168.1.1"

        # Act
        key = trusted_limiter._get_rate_limit_key(mock_request, "ip")

        # Assert — real client IP surfaced through the trusted proxy header
        assert key == "ip:10.0.0.1"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_ignored_without_trusted_proxies(
        self,
        limiter: RateLimiter,
        mock_request: Request,
    ) -> None:
        """X-Forwarded-For is ignored when trusted_proxies is not configured."""
        # Arrange — default limiter has no trusted proxies
        mock_request.headers["X-Forwarded-For"] = "10.0.0.1, 192.168.1.1"

        # Act
        key = limiter._get_rate_limit_key(mock_request, "ip")

        # Assert — direct connection IP is used, header is NOT honoured
        assert key == "ip:192.168.1.100"


class TestRateLimitMiddleware:
    """Test rate limit middleware"""

    @pytest.fixture
    def app(self):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def endpoint(request):
            return JSONResponse({"allowed": True})

        app = Starlette(routes=[Route("/test", endpoint)])
        limiter = RateLimiter(redis_client=None)
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)
        return app

    @pytest.fixture
    def client(self, app):
        from starlette.testclient import TestClient

        return TestClient(app)

    def test_middleware_adds_headers(self):
        """Test middleware adds rate limit headers when state values are set."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from starlette.testclient import TestClient

        async def endpoint(request):
            # Simulate what the @rate_limit decorator sets on request.state
            request.state.rate_limit_remaining = 99
            request.state.rate_limit_limit = 100
            request.state.rate_limit_reset = 1234567890
            return JSONResponse({"allowed": True})

        app = Starlette(routes=[Route("/test", endpoint)])
        limiter = RateLimiter(redis_client=None)
        app.add_middleware(RateLimitMiddleware, rate_limiter=limiter)

        test_client = TestClient(app)
        response = test_client.get("/test")

        assert response.status_code == 200
        assert "x-ratelimit-limit" in response.headers
        assert "x-ratelimit-remaining" in response.headers


class TestTimingMiddleware:
    """Test timing middleware"""

    @pytest.fixture
    def app(self):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def endpoint(request):
            return JSONResponse({"timed": True})

        app = Starlette(routes=[Route("/test", endpoint)])
        app.add_middleware(TimingMiddleware)
        return app

    @pytest.fixture
    def client(self, app):
        from starlette.testclient import TestClient

        return TestClient(app)

    def test_timing_middleware_creation(self):
        """Test timing middleware instantiation"""
        mock_app = Mock()
        mw = TimingMiddleware(app=mock_app)
        assert mw is not None

    def test_timing_middleware_adds_header(self, client):
        """Test timing middleware adds timing header"""
        response = client.get("/test")

        assert "x-process-time" in response.headers
        assert response.status_code == 200


class TestCompressionMiddleware:
    """Test compression middleware"""

    @pytest.fixture
    def app(self):
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def small_endpoint(request):
            return JSONResponse({"small": "data"})

        async def large_endpoint(request):
            return JSONResponse({"data": "x" * 1000})

        app = Starlette(
            routes=[Route("/small", small_endpoint), Route("/large", large_endpoint)]
        )
        app.add_middleware(CompressionMiddleware, minimum_size=100)
        return app

    @pytest.fixture
    def client(self, app):
        from starlette.testclient import TestClient

        return TestClient(app)

    def test_compression_middleware_creation(self):
        """Test compression middleware instantiation"""
        mock_app = Mock()
        mw = CompressionMiddleware(app=mock_app, minimum_size=100)
        assert mw is not None

    def test_compression_small_response(self, client):
        """Test compression not applied to small responses"""
        response = client.get("/small", headers={"accept-encoding": "gzip"})
        assert "content-encoding" not in response.headers

    def test_compression_large_response(self, client):
        """Test compression applied to large responses"""
        response = client.get("/large", headers={"accept-encoding": "gzip"})
        assert response.status_code == 200
        assert "content-encoding" in response.headers
        assert response.headers["content-encoding"] == "gzip"
