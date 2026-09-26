"""Tests for rate limiting middleware"""

import time
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from quadkit import serialization as json

from quadkit.auth.web.middleware.throttle import RateLimitMiddleware


@pytest.fixture
def mock_app():
    """Mock ASGI application."""
    app = AsyncMock()
    return app


@pytest.fixture
def rate_limit_middleware(mock_app):
    """Rate limit middleware instance with test defaults."""
    return RateLimitMiddleware(
        app=mock_app,
        rate_limit="3/minute",
        block_duration=120,
    )


@pytest.fixture
def http_scope():
    """Mock HTTP ASGI scope."""
    return {
        "type": "http",
        "method": "POST",
        "path": "/auth/login",
        "client": ("192.168.1.100", 1234),
        "headers": [],
    }


async def mock_receive():
    return {"type": "http.request", "body": b""}


class TestRateLimitMiddleware:
    """Test rate limiting middleware functionality."""

    @pytest.mark.asyncio
    async def test_non_auth_endpoint_passthrough(
        self, rate_limit_middleware, http_scope, mock_app
    ):
        """Test non-auth endpoints are not rate limited."""
        http_scope["path"] = "/api/users"
        
        send = AsyncMock()
        await rate_limit_middleware(http_scope, mock_receive, send)

        mock_app.assert_called_once()
        send.assert_not_called()  # Middleware shouldn't send anything yet, app does

    @pytest.mark.asyncio
    async def test_login_endpoint_rate_limited(
        self, rate_limit_middleware, http_scope, mock_app
    ):
        """Test login endpoint is rate limited."""
        # Set up app to simulate failure (doesn't really matter here for the block)
        
        send = AsyncMock()

        # Make multiple requests
        for i in range(4):
            # We need a new send mock for each call or clear it
            s = AsyncMock()
            await rate_limit_middleware(http_scope, mock_receive, s)
            if i < 3:
                # First 3 should pass to app
                pass
            else:
                # 4th should be blocked
                message = s.call_args_list[0][0][0]
                assert message["type"] == "http.response.start"
                assert message["status"] == 429

        # First 3 should pass through
        assert mock_app.call_count == 3

    @pytest.mark.asyncio
    async def test_register_endpoint_rate_limited(self, mock_app):
        """Test register endpoint is rate limited."""
        middleware = RateLimitMiddleware(app=mock_app, rate_limit="3/minute")
        scope = {
            "type": "http",
            "path": "/auth/register",
            "client": ("192.168.1.101", 1234)
        }

        for i in range(4):
            s = AsyncMock()
            await middleware(scope, mock_receive, s)

        assert mock_app.call_count == 3

    @pytest.mark.asyncio
    async def test_successful_login_clears_attempts(
        self, rate_limit_middleware, http_scope, mock_app
    ):
        """Test successful login clears rate limit attempts."""
        client_id = http_scope["client"][0]
        
        # 2 failed attempts
        for i in range(2):
            await rate_limit_middleware(http_scope, mock_receive, AsyncMock())
        
        assert len(rate_limit_middleware.attempts[client_id]) == 2

        # 3rd attempt: simulate success
        # When app is called, it should trigger 'send' with 200
        async def success_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        rate_limit_middleware.app = success_app
        await rate_limit_middleware(http_scope, mock_receive, AsyncMock())

        # Attempts should be cleared
        assert len(rate_limit_middleware.attempts[client_id]) == 0

    @pytest.mark.asyncio
    async def test_block_duration(self, rate_limit_middleware, http_scope, mock_app):
        """Test client is blocked for specified duration."""
        # Exhaust attempts
        for i in range(4):
            await rate_limit_middleware(http_scope, mock_receive, AsyncMock())

        # Check blocked status
        client_id = http_scope["client"][0]
        assert client_id in rate_limit_middleware.blocked

    @pytest.mark.asyncio
    async def test_retry_after_header(self, rate_limit_middleware, http_scope):
        """Test Retry-After header is set correctly."""
        # Exhaust attempts
        for i in range(4):
            send = AsyncMock()
            await rate_limit_middleware(http_scope, mock_receive, send)

        # Last one should have the header
        start_message = send.call_args_list[0][0][0]
        assert start_message["status"] == 429
        headers = dict(start_message["headers"])
        assert b"retry-after" in headers
        assert int(headers[b"retry-after"]) > 0
