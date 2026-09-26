"""Tests for HealthChecker."""

import asyncio
import pytest

from quadkit.contracts.core.health import HealthCheckCategory, HealthCheckResult, HealthStatus
from quadkit.monitor.health.checker import HealthChecker, health_checker

def test_health_checker_add_remove():
    """Test add, has, remove."""
    checker = HealthChecker()
    checker.add("test", lambda: True)
    assert checker.has("test")
    assert checker.check_names == ["test"]
    
    checker.remove("test")
    assert not checker.has("test")
    
    with pytest.raises(KeyError):
        checker.remove("nonexistent")

def test_health_checker_register():
    """Test register via decorator."""
    @health_checker("my_check")
    def my_check():
        return True
        
    checker = HealthChecker()
    checker.register(my_check)
    assert checker.has("my_check")
    
    def undecorated():
        return True
        
    with pytest.raises(ValueError):
        checker.register(undecorated)

@pytest.mark.asyncio
async def test_run_all_success():
    """Test run_all with different kinds of checks."""
    checker = HealthChecker()
    
    # Sync boolean
    checker.add("sync_bool", lambda: True)
    
    # Async boolean
    async def async_bool():
        return True
    checker.add("async_bool", async_bool)
    
    # Sync dict
    checker.add("sync_dict", lambda: {"status": "healthy", "extra": 123})
    
    # HealthCheckResult
    checker.add("result", lambda: HealthCheckResult(component="result", status=HealthStatus.HEALTHY))
    
    # Protocol-like (has health_check)
    class Proto:
        async def health_check(self):
            return HealthCheckResult(component="proto", status=HealthStatus.HEALTHY)
    checker.add("proto", Proto())
    
    results = await checker.run_all()
    assert len(results) == 5
    for result in results.values():
        assert result.status == HealthStatus.HEALTHY

@pytest.mark.asyncio
async def test_run_all_timeout():
    """Test timeout."""
    checker = HealthChecker()
    
    async def slow_check():
        await asyncio.sleep(0.5)
        return True
        
    checker.add("slow", slow_check, timeout=0.1)
    
    results = await checker.run_all()
    assert results["slow"].status == HealthStatus.UNHEALTHY
    assert "timed out" in results["slow"].message

@pytest.mark.asyncio
async def test_run_all_exception(mocker):
    """Test exception handling."""
    from quadkit.monitor.health import checker as checker_module

    checker = HealthChecker()

    def crashing_check():
        raise ValueError("crash")

    warning_spy = mocker.patch.object(checker_module, "logger")
    checker.add("crash", crashing_check)
    results = await checker.run_all()
    assert results["crash"].status == HealthStatus.UNHEALTHY
    assert results["crash"].message == "ValueError: connection check failed"
    assert "crash" not in results["crash"].message
    warning_spy.warning.assert_called_once()
    assert warning_spy.warning.call_args.kwargs["error"] == "crash"
    assert warning_spy.warning.call_args.kwargs["component"] == "crash"

def test_aggregate_status():
    """Test status aggregation."""
    checker = HealthChecker()
    
    # Empty
    assert checker.aggregate_status({}) == HealthStatus.UNKNOWN
    
    # All healthy
    res1 = {"a": HealthCheckResult(component="a", status=HealthStatus.HEALTHY)}
    assert checker.aggregate_status(res1) == HealthStatus.HEALTHY
    
    # One unhealthy
    res2 = {
        "a": HealthCheckResult(component="a", status=HealthStatus.HEALTHY),
        "b": HealthCheckResult(component="b", status=HealthStatus.UNHEALTHY),
    }
    assert checker.aggregate_status(res2) == HealthStatus.UNHEALTHY
    
    # One degraded
    res3 = {
        "a": HealthCheckResult(component="a", status=HealthStatus.HEALTHY),
        "b": HealthCheckResult(component="b", status=HealthStatus.DEGRADED),
    }
    assert checker.aggregate_status(res3) == HealthStatus.DEGRADED

@pytest.mark.asyncio
async def test_run_by_category():
    """Test run_by_category methods."""
    checker = HealthChecker()
    checker.add("liveness", lambda: True, category=HealthCheckCategory.LIVENESS)
    checker.add("readiness", lambda: True, category=HealthCheckCategory.READINESS)
    checker.add("startup", lambda: True, category=HealthCheckCategory.STARTUP)
    
    status, res = await checker.run_liveness()
    assert status == HealthStatus.HEALTHY
    assert "liveness" in res
    assert "readiness" not in res
    
    status, res = await checker.run_readiness()
    assert "readiness" in res
    assert "liveness" not in res
    
    status, res = await checker.run_startup()
    assert "startup" in res
    
    status, res = await checker.run_all_with_summary()
    assert len(res) == 3
