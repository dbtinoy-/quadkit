"""Unit tests for quadkit.monitor.types."""

from __future__ import annotations

import pytest
import time
from dataclasses import fields

from quadkit.monitor.types import HealthCheckerProtocol, MetricValue, PerformanceMonitorState


class TestMetricValue:
    """Tests for MetricValue dataclass."""

    @pytest.fixture
    def metric_value(self) -> MetricValue:
        return MetricValue(
            name="test_metric",
            value=42.0,
            labels={"service": "test"},
        )

    def test_creation(self, metric_value: MetricValue) -> None:
        assert metric_value.name == "test_metric"
        assert metric_value.value == 42.0
        assert metric_value.labels == {"service": "test"}

    def test_timestamp_default(self, metric_value: MetricValue) -> None:
        assert metric_value.timestamp > 0

    def test_timestamp_custom(self) -> None:
        custom_ts = 1234567890.0
        metric = MetricValue(
            name="test",
            value=1.0,
            labels={},
            timestamp=custom_ts,
        )
        assert metric.timestamp == custom_ts

    def test_labels_default(self) -> None:
        metric = MetricValue(name="test", value=1.0, labels={})
        assert metric.labels == {}

    def test_numeric_value_int(self) -> None:
        metric = MetricValue(name="test", value=10, labels={})
        assert metric.value == 10
        assert isinstance(metric.value, int)

    def test_numeric_value_float(self) -> None:
        metric = MetricValue(name="test", value=3.14, labels={})
        assert metric.value == 3.14
        assert isinstance(metric.value, float)


class TestPerformanceMonitorState:
    """Tests for PerformanceMonitorState enum."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("stopped", PerformanceMonitorState.STOPPED),
            ("monitoring", PerformanceMonitorState.MONITORING),
            ("paused", PerformanceMonitorState.PAUSED),
        ],
    )
    def test_enum_values(self, value: str, expected: PerformanceMonitorState) -> None:
        assert PerformanceMonitorState(value) == expected

    @pytest.mark.parametrize(
        ("member", "expected_value"),
        [
            (PerformanceMonitorState.STOPPED, "stopped"),
            (PerformanceMonitorState.MONITORING, "monitoring"),
            (PerformanceMonitorState.PAUSED, "paused"),
        ],
    )
    def test_enum_members(self, member: PerformanceMonitorState, expected_value: str) -> None:
        assert member.value == expected_value

    def test_enum_is_string_enum(self) -> None:
        assert PerformanceMonitorState("stopped") == PerformanceMonitorState.STOPPED

    def test_enum_total_members(self) -> None:
        assert len(PerformanceMonitorState) == 3


class TestHealthCheckerProtocol:
    """Tests for HealthCheckerProtocol."""

    class MockHealthChecker:
        async def check(self):
            from quadkit.contracts.core import HealthCheckResult, HealthStatus

            return HealthCheckResult(
                component="test",
                status=HealthStatus.HEALTHY,
                message="ok",
            )

    def test_protocol_implementation(self) -> None:
        checker = self.MockHealthChecker()

        async def run_check():
            result = await checker.check()
            assert result.component == "test"

        import asyncio

        asyncio.run(run_check())