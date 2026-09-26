"""Tests for CachedHealthChecker."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime, timedelta

from quadkit.monitor.health.cached import CachedHealthChecker
from quadkit.contracts.core import HealthStatus, HealthCheckResult


@pytest.fixture
def mock_db():
    # Use a real mock that doesn't have everything by default to test hasattr logic
    db = MagicMock()
    # Remove health_check attribute to force it to use execute/execute_query
    if hasattr(db, "health_check"):
        del db.health_check
    db.execute = AsyncMock()
    return db

@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.health_check = AsyncMock()
    return cache

@pytest.mark.asyncio
async def test_cached_health_checker_db_only(mock_db):
    """Test database health check logic."""
    checker = CachedHealthChecker(db_provider=mock_db, cache_ttl=0.1)
    
    # Test healthy via execute
    result = await checker.get_database_health()
    assert result.status == HealthStatus.HEALTHY
    assert result.component == "database"
    mock_db.execute.assert_awaited_once_with("SELECT 1")
    
    # Test unhealthy via exception
    mock_db.execute.side_effect = ConnectionError("offline")
    # Wait for TTL to expire if needed, but we don't have cache yet for the second call if we didn't wait
    # Actually checker._is_cache_valid will return False if we wait
    await asyncio.sleep(0.15)
    result = await checker.get_database_health()
    assert result.status == HealthStatus.UNHEALTHY
    assert result.message == "ConnectionError: connection check failed"

@pytest.mark.asyncio
async def test_cached_health_checker_redis_only(mock_cache):
    """Test redis health check logic."""
    checker = CachedHealthChecker(cache_backend=mock_cache, cache_ttl=0.1)
    
    # Test healthy
    result = await checker.get_redis_health()
    assert result.status == HealthStatus.HEALTHY
    mock_cache.health_check.assert_awaited_once()
    
    # Test unhealthy
    mock_cache.health_check.side_effect = TimeoutError("slow")
    await asyncio.sleep(0.15)
    result = await checker.get_redis_health()
    assert result.status == HealthStatus.UNHEALTHY
    assert result.message == "TimeoutError: connection check failed"

@pytest.mark.asyncio
async def test_cached_health_checker_overall(mock_db, mock_cache):
    """Test overall health aggregation."""
    checker = CachedHealthChecker(db_provider=mock_db, cache_backend=mock_cache)
    
    # Both healthy
    overall = await checker.get_overall_health()
    assert overall["status"] == "healthy"
    assert "database" in overall["components"]
    assert "redis" in overall["components"]
    
    # One unhealthy
    mock_db.execute.side_effect = ConnectionError("err")
    # Force refresh by waiting
    checker._cache_ttl = 0.01
    await asyncio.sleep(0.02)
    
    overall = await checker.get_overall_health()
    assert overall["status"] == "unhealthy"

@pytest.mark.asyncio
async def test_cached_health_checker_background_refresh(mock_db, mock_cache):
    """Test background refresh loop."""
    checker = CachedHealthChecker(db_provider=mock_db, cache_backend=mock_cache, cache_ttl=0.05)
    
    await checker.start_background_refresh()
    assert checker._running
    
    # Wait for a few iterations
    await asyncio.sleep(0.15)
    
    # Check that calls were made multiple times
    assert mock_db.execute.await_count >= 2
    assert mock_cache.health_check.await_count >= 2
    
    await checker.stop_background_refresh()
    assert not checker._running
    assert len(checker._background_tasks) == 0

@pytest.mark.asyncio
async def test_cached_health_checker_no_provider():
    """Test behavior when no providers are configured."""
    checker = CachedHealthChecker(db_provider=None, cache_backend=None)
    
    db_res = await checker.get_database_health()
    assert db_res.status == HealthStatus.UNHEALTHY
    assert "No database provider configured" in db_res.message
    
    # Mirrors the database branch: an unconfigured component is reported
    # UNHEALTHY ("not configured"), never a fake HEALTHY.
    redis_res = await checker.get_redis_health()
    assert redis_res.status == HealthStatus.UNHEALTHY
    assert "No cache backend configured" in redis_res.message


@pytest.mark.asyncio
async def test_cached_health_db_failure_leaks_nothing_but_logs_detail(mocker):
    """Raw exception strings never reach the JSON payload; full detail goes to logs."""
    from quadkit.monitor.health import cached as cached_module

    db = MagicMock()
    if hasattr(db, "health_check"):
        del db.health_check
    db.execute = AsyncMock(side_effect=ConnectionError("offline"))
    warning_spy = mocker.patch.object(cached_module, "logger")

    checker = CachedHealthChecker(db_provider=db, cache_ttl=0.1)
    result = await checker.get_database_health()

    assert result.status == HealthStatus.UNHEALTHY
    assert result.message == "ConnectionError: connection check failed"
    assert "offline" not in result.message
    warning_spy.warning.assert_called_once()
    assert warning_spy.warning.call_args.kwargs["error"] == "offline"
    assert warning_spy.warning.call_args.kwargs["component"] == "database"


@pytest.mark.asyncio
async def test_cached_health_redis_failure_leaks_nothing_but_logs_detail(mocker):
    """Same guarantee for the redis check path."""
    from quadkit.monitor.health import cached as cached_module

    cache = MagicMock()
    cache.health_check = AsyncMock(side_effect=TimeoutError("slow"))
    warning_spy = mocker.patch.object(cached_module, "logger")

    checker = CachedHealthChecker(cache_backend=cache, cache_ttl=0.1)
    result = await checker.get_redis_health()

    assert result.status == HealthStatus.UNHEALTHY
    assert result.message == "TimeoutError: connection check failed"
    assert "slow" not in result.message
    warning_spy.warning.assert_called_once()
    assert warning_spy.warning.call_args.kwargs["error"] == "slow"
    assert warning_spy.warning.call_args.kwargs["component"] == "redis"
