"""Unit tests for QueryMonitor."""

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
    with patch("quadkit.sql.monitoring.database_monitor.query.logger") as mock_log:
        yield mock_log


class TestQueryMonitor:
    """Test QueryMonitor functionality"""

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def collector(self):
        """Create a test metrics collector"""
        return InMemoryDbMetricsCollector()

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def monitor(self, collector):
        """Create a QueryMonitor instance with a small slow threshold for fast tests"""
        return QueryMonitor(collector, slow_query_threshold=0.01)

    @pytest.mark.asyncio
    async def test_init(self, collector):
        """Test QueryMonitor initialization"""
        monitor = QueryMonitor(collector, slow_query_threshold=0.05)
        assert monitor.collector == collector
        assert monitor.slow_query_threshold == 0.05

    @pytest.mark.asyncio
    async def test_monitor_query_success(self, monitor, collector):
        """Test successful query monitoring"""
        query = "SELECT * FROM users"

        async with monitor.monitor_query(query, parameters=[1], connection_id="conn1"):
            # Simulate query execution
            await asyncio.sleep(0.01)

        # Check that metrics were recorded
        assert len(collector.query_metrics) == 1
        metric = collector.query_metrics[0]
        assert metric.query == query
        assert metric.parameters == [1]
        assert metric.success is True
        assert metric.error_message is None
        assert metric.connection_id == "conn1"
        assert metric.execution_time >= 0.01

    @pytest.mark.asyncio
    async def test_monitor_query_failure(self, monitor, collector):
        """Test failed query monitoring"""
        query = "SELECT * FROM invalid_table"

        with pytest.raises(ValueError, match="Table does not exist"):
            async with monitor.monitor_query(query):
                raise ValueError("Table does not exist")

        # Check that metrics were recorded
        assert len(collector.query_metrics) == 1
        metric = collector.query_metrics[0]
        assert metric.query == query
        assert metric.success is False
        assert metric.error_message == "Table does not exist"

    @pytest.mark.asyncio
    async def test_monitor_query_slow_query_logging(
        self, monitor, collector, caplog, mock_db_logger
    ):
        """Test slow query logging"""

        caplog.set_level("WARNING")
        query = "SELECT * FROM large_table"

        async with monitor.monitor_query(query):
            await asyncio.sleep(0.02)  # Exceed threshold (0.01)

        # Check call instead of caplog
        assert mock_db_logger.warning.called
        args, _ = mock_db_logger.warning.call_args
        assert "SLOW QUERY" in args[0]
        assert query == args[2]

    @pytest.mark.asyncio
    async def test_get_stats(self, monitor, collector):
        """Test getting query statistics"""
        # Add some test metrics
        await collector.record_query_metrics(
            QueryMetrics(
                query="SELECT 1",
                parameters=None,
                execution_time=0.1,
                timestamp=datetime.now(UTC),
                success=True,
            ),
        )

        stats = await monitor.get_stats()
        assert stats["total_queries"] == 1
        assert stats["successful_queries"] == 1
        assert stats["failed_queries"] == 0


