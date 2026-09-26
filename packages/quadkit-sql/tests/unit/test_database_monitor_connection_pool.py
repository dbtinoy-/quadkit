"""Unit tests for ConnectionPoolMonitor."""

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
    with patch("quadkit.sql.monitoring.database_monitor.pool.logger") as mock_log:
        yield mock_log


class TestConnectionPoolMonitor:
    """Test ConnectionPoolMonitor functionality"""

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def collector(self):
        """Create a test metrics collector"""
        return InMemoryDbMetricsCollector()

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def monitor(self, collector):
        """Create a ConnectionPoolMonitor instance"""
        return ConnectionPoolMonitor(collector)

    @pytest.mark.asyncio
    async def test_init(self, collector):
        """Test ConnectionPoolMonitor initialization"""
        monitor = ConnectionPoolMonitor(collector)
        assert monitor.collector == collector
        assert monitor.monitoring_task is None
        assert monitor.pool is None

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, monitor):
        """Test starting and stopping pool monitoring"""
        pool = MagicMock()
        pool._active_connections = 5
        pool._total_connections = 10

        await monitor.start_monitoring(pool)
        assert monitor.pool == pool
        assert monitor.monitoring_task is not None

        await monitor.stop_monitoring()
        assert monitor.monitoring_task is None

    @pytest.mark.asyncio
    async def test_collect_pool_metrics(self, monitor, collector):
        """Test collecting pool metrics"""
        pool = MagicMock()
        pool._active_connections = 3
        pool._total_connections = 10

        monitor.pool = pool
        await monitor._collect_pool_metrics()

        # Check that metrics were recorded
        assert len(collector.connection_metrics) == 1
        metric = collector.connection_metrics[0]
        assert metric.active_connections == 3
        assert metric.total_connections == 10
        assert metric.utilization == 0.3

    @pytest.mark.asyncio
    async def test_probe_pool_executes_select_one(self, monitor):
        """Probe executes a lightweight health query through the provider."""
        provider = MagicMock()
        scoped_context = MagicMock()
        scoped_context.__aenter__ = AsyncMock(return_value=None)
        scoped_context.__aexit__ = AsyncMock(return_value=False)
        connection = MagicMock()
        connection.execute = AsyncMock()

        provider.scoped_context.return_value = scoped_context
        provider.get_scoped_connection = AsyncMock(return_value=connection)
        provider.evict_dead_connections = AsyncMock()
        monitor._provider = provider

        await monitor._probe_pool()

        connection.execute.assert_awaited_once_with("SELECT 1")
        provider.evict_dead_connections.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_probe_pool_failure_requests_eviction(self, monitor):
        """Probe failure triggers best-effort dead-connection eviction."""
        provider = MagicMock()
        scoped_context = MagicMock()
        scoped_context.__aenter__ = AsyncMock(return_value=None)
        scoped_context.__aexit__ = AsyncMock(return_value=False)

        provider.scoped_context.return_value = scoped_context
        provider.get_scoped_connection = AsyncMock(
            side_effect=ConnectionError("dead pool")
        )
        provider.evict_dead_connections = AsyncMock()
        monitor._provider = provider

        await monitor._probe_pool()

        provider.evict_dead_connections.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_probe_pool_without_eviction_support_does_not_raise(self, monitor):
        """Probe failure is tolerated when provider lacks eviction support."""

        class ProviderWithoutEviction:
            def __init__(self) -> None:
                scoped_context = MagicMock()
                scoped_context.__aenter__ = AsyncMock(return_value=None)
                scoped_context.__aexit__ = AsyncMock(return_value=False)
                self._scoped_context = scoped_context

            def scoped_context(self) -> MagicMock:
                return self._scoped_context

            async def get_scoped_connection(self) -> None:
                raise ConnectionError("dead pool")

        monitor._provider = ProviderWithoutEviction()

        await monitor._probe_pool()

    @pytest.mark.asyncio
    async def test_probe_pool_failure_logs_eviction_count(
        self, monitor, mock_db_logger
    ):
        """Probe failure logs the number of connections remaining after eviction."""
        provider = MagicMock()
        scoped_context = MagicMock()
        scoped_context.__aenter__ = AsyncMock(return_value=None)
        scoped_context.__aexit__ = AsyncMock(return_value=False)

        provider.scoped_context.return_value = scoped_context
        provider.get_scoped_connection = AsyncMock(
            side_effect=ConnectionError("dead pool")
        )
        # Provider supports eviction and returns count of remaining connections
        provider.evict_dead_connections = AsyncMock(return_value=3)
        monitor._provider = provider

        await monitor._probe_pool()

        provider.evict_dead_connections.assert_awaited_once()
        # Should log the eviction result with the count of remaining connections
        # Check that info or warning was called with a message about remaining connections
        all_calls = [str(c) for c in mock_db_logger.info.call_args_list] + [
            str(c) for c in mock_db_logger.warning.call_args_list
        ]
        # The implementation should log something like "3 connections remaining"
        # or "evicted ... 3 remaining" after calling evict_dead_connections()
        found_eviction_log = any(
            ("remaining" in call.lower() and "3" in call)
            or ("evict" in call.lower() and "3" in call)
            for call in all_calls
        )
        assert found_eviction_log, (
            f"Expected log message about eviction with count 3, but got: {all_calls}"
        )

    @pytest.mark.asyncio
    async def test_collect_pool_metrics_exception(
        self, monitor, collector, caplog, mock_db_logger
    ):
        """Test pool metrics collection with exception"""

        caplog.set_level("ERROR")
        pool = MagicMock()
        # Use PropertyMock to trigger side_effect on attribute ACCESS
        type(pool)._active_connections = PropertyMock(
            side_effect=RuntimeError("Pool error")
        )
        monitor.pool = pool

        await monitor._collect_pool_metrics()

        # Check call instead of caplog
        assert mock_db_logger.exception.called
        args, _ = mock_db_logger.exception.call_args
        assert "Error collecting pool metrics" in args[0]

    @pytest.mark.asyncio
    async def test_monitor_pool_exception_handling(
        self, monitor, collector, caplog, mock_db_logger
    ):
        """Test pool monitoring exception handling"""

        caplog.set_level("ERROR")
        pool = MagicMock()
        pool._active_connections = 5
        pool._total_connections = 10
        monitor.pool = pool

        # Mock _collect_pool_metrics to raise an exception
        async def failing_collect():
            raise RuntimeError("Monitor error")

        monitor._collect_pool_metrics = failing_collect

        # Start monitoring and let it run briefly
        await monitor.start_monitoring(pool)
        await asyncio.sleep(0.02)  # Let the monitoring task run
        await monitor.stop_monitoring()

        # Check call instead of caplog
        assert mock_db_logger.exception.called
        args, _ = mock_db_logger.exception.call_args
        assert "Error monitoring connection pool" in args[0]


