"""Tests for OpenTelemetry backend."""

import pytest

pytest.importorskip("opentelemetry", reason="Requires opentelemetry")
from unittest.mock import MagicMock, patch, AsyncMock
from quadkit.monitor.backends.opentelemetry import OpenTelemetryBackend


@pytest.mark.asyncio
async def test_otel_backend_initialization():
    """Test OTel backend initialization."""
    with patch("quadkit.monitor.backends.opentelemetry.HAS_OPENTELEMETRY", True):
        # Mocking the actual opentelemetry SDK calls in the module where they are used
        with patch("quadkit.monitor.backends.opentelemetry.MeterProvider") as mock_meter_provider, \
             patch("quadkit.monitor.backends.opentelemetry.TracerProvider") as mock_tracer_provider, \
             patch("quadkit.monitor.backends.opentelemetry.metrics") as mock_metrics, \
             patch("quadkit.monitor.backends.opentelemetry.trace") as mock_trace:
            
            backend = OpenTelemetryBackend(service_name="test-service")
            await backend.initialize()
            
            assert backend.service_name == "test-service"
            mock_meter_provider.assert_called()
            mock_tracer_provider.assert_called()
            mock_metrics.set_meter_provider.assert_called()
            mock_trace.set_tracer_provider.assert_called()


@pytest.mark.asyncio
async def test_otel_backend_no_otel():
    """Test behavior when OTel is not available."""
    with patch("quadkit.monitor.backends.opentelemetry.HAS_OPENTELEMETRY", False):
        from quadkit.monitor.exceptions import BackendNotAvailableError
        with pytest.raises(BackendNotAvailableError):
            OpenTelemetryBackend(service_name="test-service")


def test_otel_backend_record_metric():
    """Test recording a metric."""
    with patch("quadkit.monitor.backends.opentelemetry.HAS_OPENTELEMETRY", True):
        backend = OpenTelemetryBackend(service_name="test-service")
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        backend.meter = mock_meter
        
        # Correctly pass metric_type
        backend.record_metric("test_metric", 1, "counter", {"attr": "val"})
        mock_counter.add.assert_called_once_with(1, {"attr": "val"})


def test_otel_backend_create_span():
    """Test starting a span via create_span method."""
    with patch("quadkit.monitor.backends.opentelemetry.HAS_OPENTELEMETRY", True):
        backend = OpenTelemetryBackend(service_name="test-service")
        mock_tracer = MagicMock()
        backend.tracer = mock_tracer
        
        # create_span is the correct method name
        backend.create_span("test_span")
        mock_tracer.start_as_current_span.assert_called_once_with("test_span")
