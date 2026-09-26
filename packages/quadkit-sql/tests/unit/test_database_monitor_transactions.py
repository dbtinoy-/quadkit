"""Unit tests for TransactionMonitor."""

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
    with patch("quadkit.sql.monitoring.database_monitor.transaction.logger") as mock_log:
        yield mock_log


class TestTransactionMonitor:
    """Test TransactionMonitor functionality"""

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def collector(self):
        """Create a test metrics collector"""
        return InMemoryDbMetricsCollector()

    @pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def monitor(self, collector):
        """Create a TransactionMonitor instance"""
        return TransactionMonitor(collector)

    @pytest.mark.asyncio
    async def test_init(self, collector):
        """Test TransactionMonitor initialization"""
        monitor = TransactionMonitor(collector)
        assert monitor.collector == collector

    @pytest.mark.asyncio
    async def test_monitor_transaction_success(self, monitor, collector):
        """Test successful transaction monitoring"""
        transaction_id = "tx123"

        async with monitor.monitor_transaction(transaction_id):
            await asyncio.sleep(0.01)

        # Check that metrics were recorded
        assert len(collector.transaction_metrics) == 1
        metric = collector.transaction_metrics[0]
        assert metric.transaction_id == transaction_id
        assert metric.success is True
        assert metric.operation == "commit"
        assert metric.deadlock_detected is False
        assert metric.duration >= 0.01

    @pytest.mark.asyncio
    async def test_monitor_transaction_failure(self, monitor, collector):
        """Test failed transaction monitoring"""
        transaction_id = "tx456"

        with pytest.raises(RuntimeError):
            async with monitor.monitor_transaction(transaction_id):
                raise RuntimeError("Transaction failed")

        # Check that metrics were recorded
        assert len(collector.transaction_metrics) == 1
        metric = collector.transaction_metrics[0]
        assert metric.transaction_id == transaction_id
        assert metric.success is False
        assert metric.operation == "rollback"
        assert "Transaction failed" in metric.error_message

    @pytest.mark.asyncio
    async def test_monitor_transaction_deadlock_detection(self, monitor, collector):
        """Test deadlock detection in transaction failures"""
        transaction_id = "tx789"

        with pytest.raises(RuntimeError):
            async with monitor.monitor_transaction(transaction_id):
                raise RuntimeError("Deadlock detected")

        # Check deadlock detection
        assert len(collector.transaction_metrics) == 1
        metric = collector.transaction_metrics[0]
        assert metric.deadlock_detected is True

    @pytest.mark.asyncio
    async def test_get_stats(self, monitor, collector):
        """Test getting transaction statistics"""
        # Add some test metrics
        await collector.record_transaction_metrics(
            TransactionMetrics(
                transaction_id="tx1",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
                duration=0.1,
                operation="commit",
                success=True,
                deadlock_detected=False,
            ),
        )

        stats = await monitor.get_stats()
        assert stats["total_transactions"] == 1
        assert stats["successful_transactions"] == 1
        assert stats["commit_ratio"] == 1.0


