"""Extended tests for HealthCheckRegistry."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from quadkit.monitor.health.registry import HealthCheckRegistry
from quadkit.contracts.core import HealthStatus, HealthCheckResult


@pytest.mark.asyncio
async def test_health_check_registry_liveness_readiness():
    """Test liveness and readiness filtering and status aggregation."""
    registry = HealthCheckRegistry()
    
    # 1. Critical liveness check
    async def live_check():
        return HealthCheckResult(component="live", status=HealthStatus.HEALTHY)
    
    registry.add("live", live_check, category="liveness")
    
    # 2. Non-critical readiness check
    async def ready_check():
        return HealthCheckResult(component="ready", status=HealthStatus.DEGRADED)
    
    registry.add("ready", ready_check, category="readiness", critical=False)
    
    # Run liveness
    status, res = await registry.run_liveness()
    assert status == HealthStatus.HEALTHY
    assert len(res["checks"]) == 1
    assert res["checks"][0]["component"] == "live"
    
    # Run readiness
    status, res = await registry.run_readiness()
    assert status == HealthStatus.DEGRADED
    assert len(res["checks"]) == 1
    assert res["checks"][0]["component"] == "ready"
    
    # Run all
    status, details = await registry.run_all()
    assert status == HealthStatus.DEGRADED

@pytest.mark.asyncio
async def test_health_check_registry_exceptions(mocker):
    """Test handling of exceptions in checks."""
    from quadkit.monitor.health import registry as registry_module

    registry = HealthCheckRegistry()

    async def fail_check():
        raise RuntimeError("boom")

    exception_spy = mocker.patch.object(registry_module, "logger")
    registry.add("fail", fail_check, category="liveness")

    status, res = await registry.run_liveness()
    assert status == HealthStatus.UNHEALTHY
    assert res["checks"][0]["message"] == "RuntimeError: connection check failed"
    assert "boom" not in res["checks"][0]["message"]
    exception_spy.exception.assert_called_once()

@pytest.mark.asyncio
async def test_health_check_registry_critical_failure():
    """Test that critical failures trigger UNHEALTHY status."""
    registry = HealthCheckRegistry()
    
    async def fail_check():
        return HealthCheckResult(component="fail", status=HealthStatus.UNHEALTHY)
    
    # Readiness check, critical=True by default
    registry.add("fail", fail_check, category="readiness")
    
    status, res = await registry.run_readiness()
    assert status == HealthStatus.UNHEALTHY

@pytest.mark.asyncio
async def test_health_check_registry_startup():
    """Test startup check (alias for liveness)."""
    registry = HealthCheckRegistry()
    async def start_check():
        return True
    registry.add("start", start_check, category="startup")
    
    status, res = await registry.run_startup()
    assert status == HealthStatus.HEALTHY
    assert res["checks"][0]["component"] == "start"

@pytest.mark.asyncio
async def test_health_check_registry_as_health_check():
    """Test using registry as a health check itself."""
    registry = HealthCheckRegistry()
    async def c1_check():
        return True
    registry.add("c1", c1_check)
    
    result = await registry.health_check()
    assert result.component == "health_registry"
    assert result.status == HealthStatus.HEALTHY
    assert "liveness" in result.details
