"""Tests for OTel exporter registry."""

import sys
from collections.abc import Iterator

import pytest
from unittest.mock import MagicMock, patch

from quadkit.monitor.backends.exporters.otel_registry import (
    OTLPTracingExporterHandler,
    OTLPMetricsExporterHandler,
    ConsoleTracingExporterHandler,
    ConsoleMetricsExporterHandler,
    TracingExporterRegistry,
    MetricsExporterRegistry,
)


@pytest.fixture(autouse=True)
def _mock_otel_modules() -> Iterator[None]:
    """Stub optional OTel exporter modules and restore them afterwards."""
    mock_otel = MagicMock()
    entries = {
        "opentelemetry": mock_otel,
        "opentelemetry.exporter": mock_otel.exporter,
        "opentelemetry.exporter.otlp": mock_otel.exporter.otlp,
        "opentelemetry.exporter.otlp.proto": mock_otel.exporter.otlp.proto,
        "opentelemetry.exporter.otlp.proto.grpc": mock_otel.exporter.otlp.proto.grpc,
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": mock_otel.exporter.otlp.proto.grpc.trace_exporter,
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter": mock_otel.exporter.otlp.proto.grpc.metric_exporter,
        "opentelemetry.sdk": mock_otel.sdk,
        "opentelemetry.sdk.trace": mock_otel.sdk.trace,
        "opentelemetry.sdk.trace.export": mock_otel.sdk.trace.export,
        "opentelemetry.sdk.metrics": mock_otel.sdk.metrics,
        "opentelemetry.sdk.metrics.export": mock_otel.sdk.metrics.export,
    }
    saved = {name: sys.modules.get(name) for name in entries}
    sys.modules.update(entries)
    yield
    for name, module in saved.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


def test_otlp_tracing_handler():
    """Test OTLP tracing handler."""
    handler = OTLPTracingExporterHandler()
    assert handler.can_handle("otlp")
    assert not handler.can_handle("console")
    
    config = MagicMock()
    config.endpoint = "localhost:4317"
    config.headers = {"x-test": "val"}
    
    with patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter", create=True) as mock_exporter:
        handler.create_exporter(config)
        mock_exporter.assert_called_once()


def test_console_tracing_handler():
    """Test console tracing handler."""
    handler = ConsoleTracingExporterHandler()
    assert handler.can_handle("console")
    
    with patch("opentelemetry.sdk.trace.export.ConsoleSpanExporter", create=True) as mock_exporter:
        handler.create_exporter(None)
        mock_exporter.assert_called_once()


def test_otlp_metrics_handler():
    """Test OTLP metrics handler."""
    handler = OTLPMetricsExporterHandler()
    assert handler.can_handle("otlp")
    
    config = MagicMock()
    config.endpoint = "localhost:4317"
    config.headers = {"x-test": "val"}
    
    with patch("opentelemetry.exporter.otlp.proto.grpc.metric_exporter.OTLPMetricExporter", create=True) as mock_exporter:
        handler.create_exporter(config)
        mock_exporter.assert_called_once()


def test_console_metrics_handler():
    """Test console metrics handler."""
    handler = ConsoleMetricsExporterHandler()
    assert handler.can_handle("console")
    
    with patch("opentelemetry.sdk.metrics.export.ConsoleMetricExporter", create=True) as mock_exporter:
        handler.create_exporter(None)
        mock_exporter.assert_called_once()


def test_tracing_exporter_registry():
    """Test tracing exporter registry."""
    registry = TracingExporterRegistry()
    assert len(registry._handlers) == 0
    
    handler = MagicMock()
    handler.can_handle.return_value = True
    registry.register(handler)
    assert len(registry._handlers) == 1
    
    config = MagicMock()
    config.type = "custom"
    registry.create_exporter(config)
    handler.create_exporter.assert_called_once_with(config)


def test_tracing_exporter_registry_defaults():
    """Test tracing exporter registry with defaults."""
    registry = TracingExporterRegistry.with_defaults()
    # console and otlp
    assert len(registry._handlers) == 2
    
    config = MagicMock()
    config.type = "otlp"
    config.endpoint = "localhost"
    config.headers = {}
    
    with patch("opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter", create=True):
        exporter = registry.create_exporter(config)
        assert exporter is not None


def test_metrics_exporter_registry():
    """Test metrics exporter registry."""
    registry = MetricsExporterRegistry()
    assert len(registry._handlers) == 0
    
    handler = MagicMock()
    handler.can_handle.return_value = True
    registry.register(handler)
    
    config = MagicMock()
    config.type = "custom"
    registry.create_exporter(config)
    handler.create_exporter.assert_called_once_with(config)


def test_metrics_exporter_registry_defaults():
    """Test metrics exporter registry with defaults."""
    registry = MetricsExporterRegistry.with_defaults()
    assert len(registry._handlers) == 2
    
    config = MagicMock()
    config.type = "console"
    
    with patch("opentelemetry.sdk.metrics.export.ConsoleMetricExporter", create=True):
        exporter = registry.create_exporter(config)
        assert exporter is not None
