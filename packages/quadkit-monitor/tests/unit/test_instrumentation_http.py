"""Tests for HTTP instrumentation."""

import pytest
from unittest.mock import AsyncMock, MagicMock

import quadkit.monitor.instrumentation.http as http_module
from quadkit.monitor.instrumentation.http import OTelMiddleware


@pytest.fixture
def mock_asgi_app():
    async def app(scope, receive, send):
        if scope["type"] == "http":
            if scope["path"] == "/error":
                raise ValueError("app error")
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})
    return app

@pytest.fixture
def mock_otel(monkeypatch):
    """Mock OpenTelemetry components."""
    mock_tracer = MagicMock()
    mock_meter = MagicMock()
    mock_counter = MagicMock()
    mock_histogram = MagicMock()
    
    mock_meter.create_counter.return_value = mock_counter
    mock_meter.create_histogram.return_value = mock_histogram
    
    # Mock trace and metrics modules
    mock_trace = MagicMock()
    mock_trace.get_tracer.return_value = mock_tracer
    mock_metrics = MagicMock()
    mock_metrics.get_meter.return_value = mock_meter
    
    monkeypatch.setattr(http_module, "trace", mock_trace)
    monkeypatch.setattr(http_module, "metrics", mock_metrics)
    monkeypatch.setattr(http_module, "_opentelemetry_available", True)
    
    return {
        "tracer": mock_tracer,
        "counter": mock_counter,
        "histogram": mock_histogram,
    }

@pytest.mark.asyncio
async def test_otel_middleware_http(mock_otel, mock_asgi_app):
    """Test OTelMiddleware with HTTP request."""
    middleware = OTelMiddleware(mock_asgi_app)
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [(b"host", b"localhost")],
        "http_version": "1.1",
        "scheme": "http",
    }
    receive = AsyncMock()
    send = AsyncMock()
    
    await middleware(scope, receive, send)
    
    # Send should be called twice (start, body)
    assert send.call_count == 2
    
    # Request counter should be incremented
    mock_otel["counter"].add.assert_called_once()
    mock_otel["histogram"].record.assert_called_once()

@pytest.mark.asyncio
async def test_otel_middleware_http_error(mock_otel, mock_asgi_app):
    """Test OTelMiddleware with HTTP error."""
    middleware = OTelMiddleware(mock_asgi_app)
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/error",
        "headers": [],
    }
    receive = AsyncMock()
    send = AsyncMock()
    
    with pytest.raises(ValueError, match="app error"):
        await middleware(scope, receive, send)
        
    mock_otel["counter"].add.assert_called_once()
    mock_otel["histogram"].record.assert_called_once()

@pytest.mark.asyncio
async def test_otel_middleware_non_http(mock_otel, mock_asgi_app):
    """Test OTelMiddleware with non-http scope."""
    middleware = OTelMiddleware(mock_asgi_app)
    
    scope = {
        "type": "lifespan",
    }
    receive = AsyncMock()
    send = AsyncMock()
    
    await middleware(scope, receive, send)
    
    mock_otel["counter"].add.assert_not_called()

@pytest.mark.asyncio
async def test_otel_middleware_no_opentelemetry(monkeypatch, mock_asgi_app):
    """Test OTelMiddleware when opentelemetry is not available."""
    monkeypatch.setattr(http_module, "_opentelemetry_available", False)
    
    middleware = OTelMiddleware(mock_asgi_app)
    
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
    }
    receive = AsyncMock()
    send = AsyncMock()
    
    await middleware(scope, receive, send)
    
    assert send.call_count == 2
