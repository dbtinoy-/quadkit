"""Tests for monitor exceptions."""

import pytest

from quadkit.monitor.exceptions import (
    BackendNotAvailableError,
    InvalidMetricError,
    MetricNotFoundError,
    MonitorConfigurationError,
    MonitorError,
    SpanError,
    SpanNotFoundError,
)


class TestMonitorError:
    """Tests for MonitorError base exception."""

    def test_monitor_error_instantiation(self) -> None:
        """Should be able to instantiate MonitorError."""
        error = MonitorError("Test monitor error")
        assert "Test monitor error" in str(error)
        assert error._code == "QK_ERR_MONITOR_001"

    def test_monitor_error_code(self) -> None:
        """Should have correct error code."""
        error = MonitorError("Test")
        assert "QK_ERR_MONITOR_001" == error._code


class TestBackendNotAvailableError:
    """Tests for BackendNotAvailableError."""

    def test_backend_not_available_error(self) -> None:
        """Should instantiate with message."""
        error = BackendNotAvailableError("Redis unavailable")
        assert "Redis unavailable" in str(error)
        assert error._code == "QK_ERR_MONITOR_002"

    def test_backend_not_available_error_code(self) -> None:
        """Should have correct error code."""
        error = BackendNotAvailableError("Backend down")
        assert "MONITOR" in error._code


class TestMetricNotFoundError:
    """Tests for MetricNotFoundError."""

    def test_metric_not_found_error(self) -> None:
        """Should instantiate with metric name."""
        error = MetricNotFoundError("request_count")
        assert "request_count" in str(error)
        assert error._code == "QK_ERR_MONITOR_003"


class TestInvalidMetricError:
    """Tests for InvalidMetricError."""

    def test_invalid_metric_error(self) -> None:
        """Should instantiate with details."""
        error = InvalidMetricError("Invalid label name")
        assert "Invalid label name" in str(error)
        assert error._code == "QK_ERR_MONITOR_004"


class TestSpanError:
    """Tests for SpanError base exception."""

    def test_span_error(self) -> None:
        """Should instantiate."""
        error = SpanError("Span error")
        assert "Span error" in str(error)
        assert error._code == "QK_ERR_MONITOR_005"


class TestSpanNotFoundError:
    """Tests for SpanNotFoundError."""

    def test_span_not_found_error(self) -> None:
        """Should instantiate with span ID."""
        error = SpanNotFoundError("span-123")
        assert "span-123" in str(error)
        assert error._code == "QK_ERR_MONITOR_006"


class TestMonitorConfigurationError:
    """Tests for MonitorConfigurationError."""

    def test_monitor_configuration_error(self) -> None:
        """Should instantiate."""
        error = MonitorConfigurationError("Invalid config")
        assert "Invalid config" in str(error)
        assert error._code == "QK_ERR_MONITOR_007"
