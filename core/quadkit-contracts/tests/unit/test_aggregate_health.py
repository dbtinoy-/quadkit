"""Tests for contracts/core/health.py — AggregateHealthResult."""

from __future__ import annotations

from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckResult,
    HealthStatus,
)


class TestAggregateHealthResultEmpty:
    """Tests for AggregateHealthResult with no components."""

    def test_empty_components_status_unknown(self) -> None:
        """Empty aggregate has UNKNOWN status."""
        result = AggregateHealthResult()
        assert result.status == HealthStatus.UNKNOWN

    def test_empty_is_healthy_false(self) -> None:
        """Empty aggregate is not healthy."""
        result = AggregateHealthResult()
        assert result.is_healthy() is False

    def test_empty_to_dict(self) -> None:
        """Empty to_dict returns correct structure."""
        result = AggregateHealthResult()
        d = result.to_dict()
        assert d["status"] == "unknown"
        assert d["components"] == []


class TestAggregateHealthResultAllHealthy:
    """Tests for AggregateHealthResult with all healthy components."""

    def test_all_healthy_status_healthy(self) -> None:
        """All healthy components → HEALTHY status."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
                HealthCheckResult(component="cache", status=HealthStatus.HEALTHY),
            ]
        )
        assert result.status == HealthStatus.HEALTHY

    def test_all_healthy_is_healthy_true(self) -> None:
        """All healthy → is_healthy returns True."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
                HealthCheckResult(component="cache", status=HealthStatus.HEALTHY),
            ]
        )
        assert result.is_healthy() is True


class TestAggregateHealthResultWithDegraded:
    """Tests for AggregateHealthResult with degraded components."""

    def test_one_degraded_no_unhealthy(self) -> None:
        """Degraded component (no UNHEALTHY) → DEGRADED status."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
                HealthCheckResult(component="cache", status=HealthStatus.DEGRADED, message="slow"),
            ]
        )
        assert result.status == HealthStatus.DEGRADED

    def test_degraded_is_healthy_false(self) -> None:
        """Degraded → is_healthy returns False."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.DEGRADED),
            ]
        )
        assert result.is_healthy() is False


class TestAggregateHealthResultWithUnhealthy:
    """Tests for AggregateHealthResult with unhealthy components."""

    def test_one_unhealthy_overrides_degraded(self) -> None:
        """UNHEALTHY component → overall UNHEALTHY regardless of degraded."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.DEGRADED),
                HealthCheckResult(component="cache", status=HealthStatus.UNHEALTHY, error="down"),
            ]
        )
        assert result.status == HealthStatus.UNHEALTHY

    def test_unhealthy_is_healthy_false(self) -> None:
        """Unhealthy → is_healthy returns False."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.UNHEALTHY),
            ]
        )
        assert result.is_healthy() is False

    def test_multiple_unhealthy_still_unhealthy(self) -> None:
        """Multiple unhealthy components still results in UNHEALTHY."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.UNHEALTHY),
                HealthCheckResult(component="cache", status=HealthStatus.UNHEALTHY),
            ]
        )
        assert result.status == HealthStatus.UNHEALTHY


class TestAggregateHealthResultToDict:
    """Tests for AggregateHealthResult.to_dict()."""

    def test_to_dict_includes_components(self) -> None:
        """to_dict includes component results."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
            ]
        )
        d = result.to_dict()
        assert "components" in d
        assert len(d["components"]) == 1

    def test_to_dict_status_value(self) -> None:
        """to_dict status is the enum value (string)."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="db", status=HealthStatus.HEALTHY),
            ]
        )
        d = result.to_dict()
        assert d["status"] == "healthy"

    def test_to_dict_with_all_statuses(self) -> None:
        """to_dict works with different status combinations."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="a", status=HealthStatus.HEALTHY),
                HealthCheckResult(component="b", status=HealthStatus.DEGRADED),
                HealthCheckResult(component="c", status=HealthStatus.UNHEALTHY),
            ]
        )
        d = result.to_dict()
        assert d["status"] == "unhealthy"


class TestAggregateHealthResultEdgeCases:
    """Edge case tests for AggregateHealthResult."""

    def test_single_healthy_component(self) -> None:
        """Single healthy component is healthy."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="test", status=HealthStatus.HEALTHY),
            ]
        )
        assert result.is_healthy() is True
        assert result.status == HealthStatus.HEALTHY

    def test_single_degraded_component(self) -> None:
        """Single degraded component is degraded."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="test", status=HealthStatus.DEGRADED),
            ]
        )
        assert result.is_healthy() is False
        assert result.status == HealthStatus.DEGRADED

    def test_single_unhealthy_component(self) -> None:
        """Single unhealthy component is unhealthy."""
        result = AggregateHealthResult(
            components=[
                HealthCheckResult(component="test", status=HealthStatus.UNHEALTHY),
            ]
        )
        assert result.is_healthy() is False
        assert result.status == HealthStatus.UNHEALTHY
