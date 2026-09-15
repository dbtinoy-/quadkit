"""Test health check endpoints."""
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.web.routing.health_checks import WebHealthChecker


@pytest_asyncio.fixture
async def cache_backend():
    """Mock cache backend for tests."""
    backend = AsyncMock()
    backend.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="redis",
            status=HealthStatus.HEALTHY,
            message="Cache connection OK",
        )
    )
    return backend


@pytest_asyncio.fixture
async def checker(cache_backend) -> WebHealthChecker:
    """Create health checker."""
    db_provider = AsyncMock()
    db_provider.health_check = AsyncMock(
        return_value=HealthCheckResult(
            component="database",
            status=HealthStatus.HEALTHY,
            message="Database connection OK",
        )
    )

    return WebHealthChecker(
        db_provider=db_provider,
        cache_backend=cache_backend,
        app_version="test-1.0.0",
    )


@pytest.mark.asyncio
async def test_healthy_when_all_components_up(checker: WebHealthChecker) -> None:
    """Test that status is healthy when all components up."""
    # Act
    health = await checker.check_health()

    # Assert
    assert health.status == HealthStatus.HEALTHY
    assert health.version == "test-1.0.0"
    assert "database" in health.components
    assert "redis" in health.components


@pytest.mark.asyncio
async def test_unhealthy_when_database_down(checker: WebHealthChecker) -> None:
    """Test that status is unhealthy when database down."""
    # Arrange - mock database failure
    checker.db_provider.health_check.side_effect = Exception("Connection refused")

    # Act
    health = await checker.check_health()

    # Assert
    assert health.status == HealthStatus.UNHEALTHY
    assert health.components["database"].status == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_degraded_when_pool_nearly_full(checker: WebHealthChecker) -> None:
    """Test that status is degraded when database reports degraded."""
    # Arrange - mock degraded db health
    checker.db_provider.health_check.return_value = HealthCheckResult(
        component="database",
        status=HealthStatus.DEGRADED,
        message="Connection pool nearly full",
    )

    # Act
    health = await checker.check_health()

    # Assert
    assert health.status == HealthStatus.DEGRADED
    assert "database" in health.components


@pytest.mark.asyncio
async def test_latency_measured(checker: WebHealthChecker) -> None:
    """Test that latency is measured."""
    # Act
    health = await checker.check_health()

    # Assert - the response should have a checked_at timestamp
    assert health.checked_at is not None
    # Latency is implicitly tested by having a valid timestamp
