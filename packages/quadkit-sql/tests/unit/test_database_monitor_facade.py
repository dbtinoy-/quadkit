"""Unit tests for the DatabaseMonitor facade."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None  # type: ignore[assignment]
from quadkit.sql.monitoring.database_monitor import (
    ConnectionPoolMonitor,
    DatabaseHealthChecker,
    DatabaseMonitor,
    QueryMonitor,
    TransactionMonitor,
)
from quadkit.sql.monitoring.metrics import (
    HealthStatus,
    InMemoryDbMetricsCollector,
    QueryMetrics,
    TransactionMetrics,
)


@pytest.fixture(autouse=True)
def mock_db_logger():
    """Patch the db.monitor logger to use a standard library logger so caplog works."""
    with patch("quadkit.sql.monitoring.database_monitor.facade.logger") as mock_log:
        yield mock_log


class TestDatabaseMonitor:
    """Test DatabaseMonitor functionality"""

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def monitor(self):
        """Create a DatabaseMonitor instance"""
        return DatabaseMonitor()

    @pytest.mark.asyncio
    async def test_init(self):
        """Test DatabaseMonitor initialization"""
        monitor = DatabaseMonitor()
        assert isinstance(monitor.collector, InMemoryDbMetricsCollector)
        assert isinstance(monitor.query_monitor, QueryMonitor)
        assert isinstance(monitor.transaction_monitor, TransactionMonitor)
        assert isinstance(monitor.health_checker, DatabaseHealthChecker)
        assert isinstance(monitor.pool_monitor, ConnectionPoolMonitor)

    @pytest.mark.asyncio
    async def test_init_with_custom_collector(self):
        """Test DatabaseMonitor with custom collector"""
        collector = InMemoryDbMetricsCollector()
        monitor = DatabaseMonitor(collector)
        assert monitor.collector == collector

    @pytest.mark.asyncio
    async def test_get_monitors(self, monitor):
        """Test getting monitor instances"""
        assert isinstance(monitor.get_query_monitor(), QueryMonitor)
        assert isinstance(monitor.get_transaction_monitor(), TransactionMonitor)
        assert isinstance(monitor.get_health_checker(), DatabaseHealthChecker)

    @pytest.mark.asyncio
    async def test_get_stats(self, monitor):
        """Test getting comprehensive statistics"""
        stats = await monitor.get_stats()
        assert "query_stats" in stats
        assert "connection_stats" in stats
        assert "transaction_stats" in stats
        assert "timestamp" in stats

    @pytest.mark.asyncio
    async def test_perform_health_check_with_pool(self, monitor):
        """Test performing health check with connection pool"""
        pool = MagicMock()
        pool._active_connections = 5
        pool._total_connections = 10

        with patch.object(
            monitor.health_checker,
            "check_database_health",
            new_callable=AsyncMock,
        ) as mock_db_check:
            mock_db_check.return_value = HealthStatus(
                component="database",
                status="healthy",
                message="OK",
                timestamp=datetime.now(UTC),
            )

            result = await monitor.perform_health_check("sqlite:///test.db", pool=pool)

            assert "checks" in result
            assert len(result["checks"]) >= 2  # Database + pool checks

    @pytest.mark.asyncio
    async def test_perform_health_check_critical_status(self, monitor):
        """Test health check aggregation with critical status"""
        with (
            patch.object(
                monitor.health_checker,
                "check_database_health",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch.object(
                monitor.health_checker,
                "check_performance_health",
                new_callable=AsyncMock,
            ) as mock_perf_check,
        ):
            mock_db_check.return_value = HealthStatus(
                component="database",
                status="critical",
                message="DB down",
                timestamp=datetime.now(UTC),
            )
            mock_perf_check.return_value = []

            result = await monitor.perform_health_check("sqlite:///test.db")

            assert result["overall_status"] == "critical"

    @pytest.mark.asyncio
    async def test_perform_health_check_warning_status(self, monitor):
        """Test health check aggregation with warning status"""
        with (
            patch.object(
                monitor.health_checker,
                "check_database_health",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch.object(
                monitor.health_checker,
                "check_performance_health",
                new_callable=AsyncMock,
            ) as mock_perf_check,
        ):
            mock_db_check.return_value = HealthStatus(
                component="database",
                status="warning",
                message="DB slow",
                timestamp=datetime.now(UTC),
            )
            mock_perf_check.return_value = []

            result = await monitor.perform_health_check("sqlite:///test.db")

            assert result["overall_status"] == "warning"

    @pytest.mark.asyncio
    async def test_perform_health_check_healthy_status(self, monitor):
        """Test health check aggregation with healthy status"""
        with (
            patch.object(
                monitor.health_checker,
                "check_database_health",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch.object(
                monitor.health_checker,
                "check_performance_health",
                new_callable=AsyncMock,
            ) as mock_perf_check,
        ):
            mock_db_check.return_value = HealthStatus(
                component="database",
                status="healthy",
                message="OK",
                timestamp=datetime.now(UTC),
            )
            mock_perf_check.return_value = []

            result = await monitor.perform_health_check("sqlite:///test.db")

            assert result["overall_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_perform_health_check_unknown_status(self, monitor):
        """Test health check aggregation with unknown status"""
        with (
            patch.object(
                monitor.health_checker,
                "check_database_health",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch.object(
                monitor.health_checker,
                "check_performance_health",
                new_callable=AsyncMock,
            ) as mock_perf_check,
        ):
            mock_db_check.return_value = HealthStatus(
                component="database",
                status="unknown",
                message="Unknown",
                timestamp=datetime.now(UTC),
            )
            mock_perf_check.return_value = []

            result = await monitor.perform_health_check("sqlite:///test.db")

            assert result["overall_status"] == "unknown"

    @pytest.mark.asyncio
    async def test_start_stop_pool_monitoring(self, monitor):
        """Test pool monitoring lifecycle"""
        pool = MagicMock()

        await monitor.start_pool_monitoring(pool)
        assert monitor.pool_monitor.pool == pool

        await monitor.stop_pool_monitoring()
        assert monitor.pool_monitor.monitoring_task is None

    @pytest.mark.asyncio
    async def test_start_pool_monitoring_uses_pool_as_provider_when_supported(
        self,
        monitor,
    ):
        """Provider-capable pools are threaded through for active probing."""
        pool = MagicMock()
        pool.scoped_context = MagicMock()

        await monitor.start_pool_monitoring(pool)

        assert monitor.pool_monitor.pool == pool
        assert monitor.pool_monitor._provider == pool

        await monitor.stop_pool_monitoring()

    @pytest.mark.asyncio
    async def test_start_pool_monitoring_allows_explicit_provider(
        self,
        monitor,
    ):
        """Explicit provider overrides pool inference."""
        pool = MagicMock()
        provider = MagicMock()

        await monitor.start_pool_monitoring(pool, provider=provider)

        assert monitor.pool_monitor.pool == pool
        assert monitor.pool_monitor._provider == provider

        await monitor.stop_pool_monitoring()
