"""Tests for monitor CLI doctor."""

import os
from unittest.mock import patch
from quadkit.monitor.cli.doctor import check_monitor_config, check_otel_endpoint


def test_check_monitor_config():
    """Test check_monitor_config stub."""
    result = check_monitor_config()
    assert result["status"] == "ok"
    assert "not yet implemented" in str(result["message"])

def test_check_otel_endpoint_not_set():
    """Test check_otel_endpoint when env var is missing."""
    with patch.dict(os.environ, {}, clear=True):
        result = check_otel_endpoint()
        assert result["status"] == "warning"
        assert "not set" in result["message"]

def test_check_otel_endpoint_set():
    """Test check_otel_endpoint when env var is set."""
    with patch.dict(os.environ, {"OTEL_EXPORTER_OTLP_ENDPOINT": "localhost:4317"}):
        result = check_otel_endpoint()
        assert result["status"] == "ok"
        assert "localhost:4317" in result["message"]
