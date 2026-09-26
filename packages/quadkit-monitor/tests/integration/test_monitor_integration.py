"""Integration tests for Quadkit Monitor package"""

from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.serialization import loads
from quadkit.monitor import (
    HealthCheckProvider,
    MetricsCollectorProtocol,
    MonitorProvider,
    PrometheusMiddleware,
    Tracer,
)


class TestMiddleware:
    """Test middleware functionality"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_prometheus_middleware_metrics_endpoint(self):
        """Test Prometheus middleware serves metrics"""
        middleware = PrometheusMiddleware()

        # Mock ASGI send function
        sent_responses = []

        async def mock_send(message):
            sent_responses.append(message)

        # Simulate GET /metrics request
        scope = {"type": "http", "method": "GET", "path": "/metrics"}

        await middleware(scope, None, mock_send)

        # Check response
        assert len(sent_responses) == 2
        assert sent_responses[0]["type"] == "http.response.start"
        assert sent_responses[0]["status"] == 200
        assert sent_responses[1]["type"] == "http.response.body"

        # Check metrics output contains expected format
        metrics_body = sent_responses[1]["body"].decode("utf-8")
        assert "# HELP" in metrics_body
        assert "# TYPE" in metrics_body

    @pytest.mark.skip(
        reason="Health check testing requires source code path resolution",
    )
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check_provider(self):
        """Test health check provider"""
        provider = HealthCheckProvider()

        # Mock ASGI send function
        sent_responses = []

        async def mock_send(message):
            sent_responses.append(message)

        # Simulate GET /health request
        scope = {"type": "http", "method": "GET", "path": "/health"}

        await provider(scope, None, mock_send)

        # Check response
        assert len(sent_responses) == 2
        assert sent_responses[0]["type"] == "http.response.start"
        assert sent_responses[0]["status"] == 200
        assert sent_responses[1]["type"] == "http.response.body"

        # Check health response
        health_body = sent_responses[1]["body"].decode("utf-8")
        health_data = loads(health_body)
        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
        assert "checks" in health_data


class TestMonitorProvider:
    """Test MonitorProvider"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_provider_creation(self):
        """Test monitor provider creation"""
        # Create a mock backend
        mock_backend = Mock()
        mock_backend.initialize = AsyncMock()
        mock_backend.shutdown = AsyncMock()

        provider = MonitorProvider(mock_backend)

        assert isinstance(provider.metrics_collector, MetricsCollectorProtocol)
        # Tracing is composed eagerly from in-memory defaults, and register()
        # re-composes when the orchestrator injects the yaml section later.
        assert isinstance(provider.tracer, Tracer)

    @pytest.mark.asyncio
    async def test_provider_lifecycle(self):
        """Test provider lifecycle methods"""
        from unittest.mock import AsyncMock as AsyncMock_

        mock_backend = Mock()
        mock_backend.initialize = AsyncMock()
        mock_backend.shutdown = AsyncMock()

        provider = MonitorProvider(mock_backend)
        
        # Mock container that returns None for optional resolutions
        mock_container = Mock()
        mock_container.resolve_optional = AsyncMock_(return_value=None)
        mock_container.resolve = AsyncMock_(return_value=None)

        await provider.boot(mock_container)
        mock_backend.initialize.assert_called_once()
        mock_container.resolve_optional.assert_called()

        await provider.shutdown()
        mock_backend.shutdown.assert_called_once()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test provider health check"""
        mock_backend = Mock()
        provider = MonitorProvider(mock_backend)

        health = await provider.health_check()
        assert health.status.value == "healthy"
        assert "metrics_count" in health.details
        assert "backend_type" in health.details
