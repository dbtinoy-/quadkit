"""Tests for PrometheusExporter."""

import pytest
from unittest.mock import MagicMock, patch
from quadkit.monitor.metrics.prometheus import PrometheusExporter, get_prometheus_exporter


def test_prometheus_exporter_creation():
    """Test creating PrometheusExporter."""
    with patch("quadkit.monitor.metrics.prometheus.CollectorRegistry") as mock_registry_class:
        exporter = PrometheusExporter()
        assert exporter.registry is not None
        mock_registry_class.assert_called_once()

def test_prometheus_exporter_get_or_create_metrics():
    """Test get-or-create behavior for various metric types."""
    with patch("quadkit.monitor.metrics.prometheus.Counter") as mock_counter_class, \
         patch("quadkit.monitor.metrics.prometheus.Gauge") as mock_gauge_class, \
         patch("quadkit.monitor.metrics.prometheus.Histogram") as mock_hist_class, \
         patch("quadkit.monitor.metrics.prometheus.Summary") as mock_summary_class:
        
        exporter = PrometheusExporter(registry=MagicMock())
        
        # Counter
        c1 = exporter.get_or_create_counter("c1", "desc", ["l1"])
        c1_again = exporter.get_or_create_counter("c1")
        assert c1 is c1_again
        mock_counter_class.assert_called_once()
        
        # Gauge
        g1 = exporter.get_or_create_gauge("g1")
        mock_gauge_class.assert_called_once()
        
        # Histogram with buckets
        h1 = exporter.get_or_create_histogram("h1", buckets=[0.1, 0.5])
        mock_hist_class.assert_called_once()
        assert "buckets" in mock_hist_class.call_args[1]
        
        # Summary
        s1 = exporter.get_or_create_summary("s1")
        mock_summary_class.assert_called_once()

def test_prometheus_exporter_export():
    """Test exporting metrics."""
    with patch("quadkit.monitor.metrics.prometheus.generate_latest", return_value=b"metrics_data"):
        exporter = PrometheusExporter(registry=MagicMock())
        assert exporter.export() == b"metrics_data"
        assert "text/plain" in exporter.content_type

def test_get_prometheus_exporter():
    """Test singleton getter."""
    assert isinstance(get_prometheus_exporter(), PrometheusExporter)

def test_prometheus_exporter_no_prometheus():
    """Test behavior when prometheus_client is not installed."""
    with patch("quadkit.monitor.metrics.prometheus.Counter", None), \
         patch("quadkit.monitor.metrics.prometheus.Gauge", None):
        exporter = PrometheusExporter()
        assert exporter.get_or_create_counter("c") is None
        assert exporter.get_or_create_gauge("g") is None
        
        # Test export fallback
        with patch("quadkit.monitor.metrics.prometheus.generate_latest", None):
            assert exporter.export() == b""
