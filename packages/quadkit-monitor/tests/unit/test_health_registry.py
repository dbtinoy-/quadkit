import pytest

from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.monitor.health.registry import HealthCheckRegistry


async def _degraded_check() -> HealthCheckResult:
    return HealthCheckResult(component="infra:llm", status=HealthStatus.DEGRADED)


async def _unhealthy_check() -> HealthCheckResult:
    return HealthCheckResult(component="infra:llm", status=HealthStatus.UNHEALTHY)


class TestHealthCheckRegistry:
    @pytest.mark.asyncio
    async def test_readiness_checks_are_critical_by_default(self) -> None:
        registry = HealthCheckRegistry()

        registry.add(
            "infra:llm",
            _degraded_check,
            category=HealthCheckCategory.READINESS,
        )

        status, readiness = await registry.run_readiness()

        assert status == HealthStatus.UNHEALTHY
        assert readiness["status"] == HealthStatus.UNHEALTHY.value

    @pytest.mark.asyncio
    async def test_noncritical_degraded_readiness_aggregates_to_degraded(self) -> None:
        registry = HealthCheckRegistry()

        registry.add(
            "infra:llm",
            _degraded_check,
            critical=False,
            category=HealthCheckCategory.READINESS,
        )

        status, readiness = await registry.run_readiness()

        assert status == HealthStatus.DEGRADED
        assert readiness["status"] == HealthStatus.DEGRADED.value

    @pytest.mark.asyncio
    async def test_noncritical_unhealthy_readiness_aggregates_to_degraded(self) -> None:
        registry = HealthCheckRegistry()

        registry.add(
            "infra:llm",
            _unhealthy_check,
            critical=False,
            category=HealthCheckCategory.READINESS,
        )

        status, readiness = await registry.run_readiness()

        assert status == HealthStatus.DEGRADED
        assert readiness["status"] == HealthStatus.DEGRADED.value
        assert readiness["checks"][0]["status"] == HealthStatus.UNHEALTHY.value
