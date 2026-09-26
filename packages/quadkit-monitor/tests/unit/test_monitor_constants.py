"""Unit tests for quadkit.monitor.constants."""

from __future__ import annotations

import pytest

from quadkit.monitor import constants


class TestVersion:
    """Tests for version constants."""

    def test_version_not_empty(self) -> None:
        assert constants.__version__
        assert len(constants.__version__) > 0


class TestEnvironmentPrefixes:
    """Tests for environment variable prefixes."""

    def test_env_prefix(self) -> None:
        assert constants.ENV_PREFIX == "QK_MONITOR__"

    def test_env_nested_delimiter(self) -> None:
        assert constants.ENV_NESTED_DELIMITER == "__"


class TestDefaultConfiguration:
    """Tests for default configuration values."""

    def test_default_service_name(self) -> None:
        assert constants.DEFAULT_SERVICE_NAME == "quadkit-service"

    def test_default_prometheus_port(self) -> None:
        assert constants.DEFAULT_PROMETHEUS_PORT == 8000
        assert isinstance(constants.DEFAULT_PROMETHEUS_PORT, int)

    def test_default_otel_endpoint(self) -> None:
        assert constants.DEFAULT_OTEL_ENDPOINT is None

    def test_default_max_spans(self) -> None:
        assert constants.DEFAULT_MAX_SPANS == 1000
        assert isinstance(constants.DEFAULT_MAX_SPANS, int)

    def test_default_health_check_interval(self) -> None:
        assert constants.DEFAULT_HEALTH_CHECK_INTERVAL == 30
        assert isinstance(constants.DEFAULT_HEALTH_CHECK_INTERVAL, int)


class TestMetricPrefixes:
    """Tests for metric name prefixes."""

    def test_metric_prefix(self) -> None:
        assert constants.METRIC_PREFIX == "quadkit_"

    def test_request_total_metric(self) -> None:
        assert constants.REQUEST_TOTAL_METRIC == "quadkit_requests_total"

    def test_active_connections_metric(self) -> None:
        assert constants.ACTIVE_CONNECTIONS_METRIC == "quadkit_active_connections"

    def test_request_duration_metric(self) -> None:
        assert constants.REQUEST_DURATION_METRIC == "quadkit_request_duration_seconds"


class TestDefaultHistogramBuckets:
    """Tests for default histogram buckets."""

    def test_buckets_type(self) -> None:
        assert isinstance(constants.DEFAULT_DURATION_BUCKETS, tuple)

    def test_buckets_values(self) -> None:
        assert constants.DEFAULT_DURATION_BUCKETS == (0.1, 0.5, 1.0, 2.0, 5.0, 10.0)

    def test_buckets_length(self) -> None:
        assert len(constants.DEFAULT_DURATION_BUCKETS) == 6

    def test_buckets_increasing(self) -> None:
        buckets = constants.DEFAULT_DURATION_BUCKETS
        for i in range(len(buckets) - 1):
            assert buckets[i] < buckets[i + 1]


class TestExports:
    """Tests for __all__ exports."""

    def test_all_contains_expected(self) -> None:
        expected = [
            "ACTIVE_CONNECTIONS_METRIC",
            "DEFAULT_DURATION_BUCKETS",
            "DEFAULT_HEALTH_CHECK_INTERVAL",
            "DEFAULT_MAX_SPANS",
            "DEFAULT_OTEL_ENDPOINT",
            "DEFAULT_PROMETHEUS_PORT",
            "DEFAULT_SERVICE_NAME",
            "ENV_NESTED_DELIMITER",
            "ENV_PREFIX",
            "METRIC_PREFIX",
            "REQUEST_DURATION_METRIC",
            "REQUEST_TOTAL_METRIC",
        ]
        assert constants.__all__ == expected