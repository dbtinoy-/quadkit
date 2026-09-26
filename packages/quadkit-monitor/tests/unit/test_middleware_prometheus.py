"""Tests for Prometheus middleware."""

import asyncio
from unittest.mock import AsyncMock

import pytest

import quadkit.monitor.middleware.prometheus as prometheus_module
from quadkit.monitor.middleware.prometheus import PrometheusMiddleware


@pytest.fixture
def mock_asgi_app():
    async def app(scope, receive, send):
        if scope["type"] == "http":
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})
    return app

@pytest.mark.asyncio
async def test_prometheus_middleware_http(mock_asgi_app):
    """Test PrometheusMiddleware with HTTP request."""
    # Force PROMETHEUS_AVAILABLE = False to test internal formatting fallback
    original_prometheus_available = prometheus_module.PROMETHEUS_AVAILABLE
    prometheus_module.PROMETHEUS_AVAILABLE = False
    
    try:
        middleware = PrometheusMiddleware(path="/metrics")
        middleware.set_next_app(mock_asgi_app)
        
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
        }
        receive = AsyncMock()
        send = AsyncMock()
        
        await middleware(scope, receive, send)
        
        assert send.call_count == 2
        
        # Test serving metrics
        metrics_scope = {
            "type": "http",
            "method": "GET",
            "path": "/metrics",
        }
        metrics_send = AsyncMock()
        await middleware(metrics_scope, receive, metrics_send)
        
        # Check if response start was sent
        assert metrics_send.call_args_list[0][0][0]["status"] == 200
    finally:
        prometheus_module.PROMETHEUS_AVAILABLE = original_prometheus_available

@pytest.mark.asyncio
async def test_prometheus_middleware_non_http():
    """Non-http scopes are forwarded to the wired inner app."""
    calls: list[str] = []

    async def app(scope, receive, send):
        calls.append(scope["type"])

    middleware = PrometheusMiddleware(app)
    scope = {"type": "lifespan"}

    await middleware(scope, AsyncMock(), AsyncMock())

    assert calls == ["lifespan"]


@pytest.mark.asyncio
async def test_prometheus_middleware_non_http_unwired_drops_without_hanging():
    """Without an inner app, non-http scopes are dropped (never hang)."""
    middleware = PrometheusMiddleware()

    scope = {"type": "websocket"}

    # Regression: previously this awaited a no-op coroutine and hung.
    await asyncio.wait_for(middleware(scope, AsyncMock(), AsyncMock()), timeout=2.0)


@pytest.mark.asyncio
async def test_prometheus_middleware_app_positional_constructor():
    """The inner app can be passed positionally (standard ASGI middleware)."""
    mock_asgi_app = AsyncMock()
    middleware = PrometheusMiddleware(mock_asgi_app)

    scope = {"type": "lifespan"}

    await middleware(scope, AsyncMock(), AsyncMock())

    assert mock_asgi_app.await_count == 1


@pytest.mark.asyncio
async def test_prometheus_middleware_rejects_missing_token():
    """Metrics endpoint returns 401 when auth_token is configured but missing."""
    middleware = PrometheusMiddleware(auth_token="s3cret")
    scope = {"type": "http", "method": "GET", "path": "/metrics"}
    send = AsyncMock()

    await middleware(scope, AsyncMock(), send)

    assert send.call_args_list[0][0][0]["status"] == 401


@pytest.mark.asyncio
async def test_prometheus_middleware_rejects_wrong_token():
    """Metrics endpoint returns 401 for a mismatched bearer token."""
    middleware = PrometheusMiddleware(auth_token="s3cret")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/metrics",
        "headers": [(b"authorization", b"Bearer wrong")],
    }
    send = AsyncMock()

    await middleware(scope, AsyncMock(), send)

    assert send.call_args_list[0][0][0]["status"] == 401


@pytest.mark.asyncio
async def test_prometheus_middleware_accepts_matching_token():
    """Metrics endpoint serves 200 for the correct bearer token."""
    middleware = PrometheusMiddleware(auth_token="s3cret")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/metrics",
        "headers": [(b"authorization", b"Bearer s3cret")],
    }
    send = AsyncMock()

    await middleware(scope, AsyncMock(), send)

    assert send.call_args_list[0][0][0]["status"] == 200


@pytest.mark.asyncio
async def test_prometheus_middleware_other_paths_pass_through_with_token(mock_asgi_app):
    """Non-endpoint requests are unaffected by an configured auth_token."""
    middleware = PrometheusMiddleware(auth_token="s3cret")
    middleware.set_next_app(mock_asgi_app)
    scope = {"type": "http", "method": "GET", "path": "/test"}
    send = AsyncMock()

    await middleware(scope, AsyncMock(), send)

    assert send.call_count == 2
