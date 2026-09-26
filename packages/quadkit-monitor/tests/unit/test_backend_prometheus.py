"""Tests for Prometheus backend."""

import pytest
from unittest.mock import MagicMock, patch
from quadkit.monitor.backends.prometheus import PrometheusBackend
from quadkit.monitor.exceptions import BackendNotAvailableError


@pytest.mark.asyncio
async def test_prometheus_backend_initialization():
    """Test Prometheus backend initialization."""
    with patch("quadkit.monitor.backends.prometheus.HAS_PROMETHEUS", True):
        with patch("quadkit.monitor.backends.prometheus.start_http_server") as mock_start_server:
            backend = PrometheusBackend(port=8888)
            await backend.initialize()
            mock_start_server.assert_called_once_with(8888)

@pytest.mark.asyncio
async def test_prometheus_backend_initialization_error():
    """Test Prometheus backend initialization with error (should not fail)."""
    with patch("quadkit.monitor.backends.prometheus.HAS_PROMETHEUS", True):
        with patch("quadkit.monitor.backends.prometheus.start_http_server", side_effect=OSError("already in use")):
            backend = PrometheusBackend()
            await backend.initialize()
            # Should log warning but not raise exception

@pytest.mark.asyncio
async def test_prometheus_backend_no_prometheus():
    """Test error when prometheus-client is not available."""
    with patch("quadkit.monitor.backends.prometheus.HAS_PROMETHEUS", False):
        with pytest.raises(BackendNotAvailableError):
            PrometheusBackend()

def test_prometheus_backend_record_metric():
    """Test recording metrics."""
    with patch("quadkit.monitor.backends.prometheus.HAS_PROMETHEUS", True):
        with patch("quadkit.monitor.backends.prometheus.PromCounter") as mock_counter, \
             patch("quadkit.monitor.backends.prometheus.PromGauge") as mock_gauge, \
             patch("quadkit.monitor.backends.prometheus.PromHistogram") as mock_hist:
            
            # Setup mock behavior
            mock_counter.return_value.labels.return_value.inc = MagicMock()
            mock_gauge.return_value.labels.return_value.set = MagicMock()
            mock_hist.return_value.labels.return_value.observe = MagicMock()
            
            backend = PrometheusBackend()
            
            # Counter
            backend.record_metric("c1", 5, "counter", {"tag": "v1"})
            mock_counter.assert_called()
            
            # Gauge
            backend.record_metric("g1", 10, "gauge")
            mock_gauge.assert_called()
            
            # Histogram
            backend.record_metric("h1", 0.5, "histogram")
            mock_hist.assert_called()

def test_prometheus_backend_create_span():
    """Test span creation (no-op)."""
    with patch("quadkit.monitor.backends.prometheus.HAS_PROMETHEUS", True):
        backend = PrometheusBackend()
        span = backend.create_span("test")
        assert span.name == "test"
        assert span.context.trace_id == "prometheus-no-trace"
