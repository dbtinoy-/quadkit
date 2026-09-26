"""HealthCheckRegistry.run_check runs a single named check."""

from __future__ import annotations

import pytest

from quadkit.contracts.core import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.monitor.health.registry import HealthCheckRegistry


@pytest.mark.asyncio
async def test_run_check_returns_unknown_for_missing() -> None:
    registry = HealthCheckRegistry()
    result = await registry.run_check("does_not_exist")
    assert result["status"] in {"unknown", "UNKNOWN"}


@pytest.mark.asyncio
async def test_run_check_runs_registered_liveness_check() -> None:
    async def _healthy() -> HealthCheckResult:
        return HealthCheckResult(component="sql", status=HealthStatus.HEALTHY)

    registry = HealthCheckRegistry()
    registry.add("sql", _healthy, category=HealthCheckCategory.LIVENESS)
    result = await registry.run_check("sql")
    assert result["status"] == HealthStatus.HEALTHY.value
    assert result["component"] == "sql"


@pytest.mark.asyncio
async def test_run_check_runs_registered_readiness_check() -> None:
    async def _degraded() -> HealthCheckResult:
        return HealthCheckResult(component="cache", status=HealthStatus.DEGRADED)

    registry = HealthCheckRegistry()
    registry.add("cache", _degraded, category=HealthCheckCategory.READINESS)
    result = await registry.run_check("cache")
    assert result["status"] == HealthStatus.DEGRADED.value


__all__ = [
    "test_run_check_returns_unknown_for_missing",
    "test_run_check_runs_registered_liveness_check",
    "test_run_check_runs_registered_readiness_check",
]
