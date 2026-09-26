"""DatabaseMonitor slow-query capture and integration tests."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from quadkit.sql.monitoring import (
    DatabaseMonitor,
    InMemoryDbMetricsCollector,
    QueryMetrics,
)


class TestDatabaseMonitor:
    """Test DatabaseMonitor functionality."""

    @pytest.fixture
    def monitor(self):
        collector = InMemoryDbMetricsCollector()
        return DatabaseMonitor(collector)

    @pytest.mark.asyncio
    async def test_monitor_creation(self, monitor):
        assert monitor is not None
        assert hasattr(monitor, "get_query_monitor")
        assert hasattr(monitor, "get_transaction_monitor")
        assert hasattr(monitor, "get_health_checker")
        assert hasattr(monitor, "start_pool_monitoring")
        assert hasattr(monitor, "stop_pool_monitoring")

    @pytest.mark.asyncio
    async def test_monitor_stats(self, monitor):
        stats = await monitor.get_stats()

        assert "query_stats" in stats
        assert "connection_stats" in stats
        assert "transaction_stats" in stats
        assert "timestamp" in stats

        query_stats = stats["query_stats"]
        assert "total_queries" in query_stats
        assert "successful_queries" in query_stats
        assert "failed_queries" in query_stats

        txn_stats = stats["transaction_stats"]
        assert "total_transactions" in txn_stats
        assert "successful_transactions" in txn_stats
        assert "failed_transactions" in txn_stats

    @pytest.mark.asyncio
    async def test_query_monitor_context_manager(self, monitor):
        query_monitor = monitor.get_query_monitor()

        async with query_monitor.monitor_query(
            query="SELECT * FROM users WHERE id = ?",
            parameters=[123],
            connection_id="test_conn",
        ):
            await asyncio.sleep(0.01)

        stats = await query_monitor.get_stats()
        assert stats["total_queries"] == 1
        assert stats["successful_queries"] == 1

    @pytest.mark.asyncio
    async def test_query_monitor_with_exception(self, monitor):
        query_monitor = monitor.get_query_monitor()

        with pytest.raises(ValueError):
            async with query_monitor.monitor_query(
                query="SELECT * FROM invalid_table", connection_id="test_conn",
            ):
                raise ValueError("Query failed")

        stats = await query_monitor.get_stats()
        assert stats["total_queries"] == 1
        assert stats["failed_queries"] == 1

    @pytest.mark.asyncio
    async def test_connection_pool_monitoring(self, monitor):
        mock_pool = MagicMock(spec=["_active_connections", "_total_connections"])
        mock_pool._active_connections = 5
        mock_pool._total_connections = 10

        await monitor.start_pool_monitoring(mock_pool)

        await asyncio.sleep(0.02)

        await monitor.stop_pool_monitoring()

    @pytest.mark.asyncio
    async def test_transaction_monitoring(self, monitor):
        txn_monitor = monitor.get_transaction_monitor()

        async with txn_monitor.monitor_transaction("test_transaction_1"):
            await asyncio.sleep(0.01)

        stats = await txn_monitor.get_stats()
        assert stats["total_transactions"] == 1
        assert stats["successful_transactions"] == 1
        assert stats["commit_count"] == 1

    @pytest.mark.asyncio
    async def test_health_checker(self, monitor, tmp_path):
        health_checker = monitor.get_health_checker()

        conn_str = "sqlite:///:memory:"

        health = await health_checker.check_database_health(conn_str, timeout=1.0)
        assert health.component == "database"
        assert (
            health.status == "healthy"
        ), f"status={health.status}, message={health.message}"
        assert "successful" in health.message
        assert health.timestamp is not None

    @pytest.mark.asyncio
    async def test_performance_baselines(self, monitor):
        health_checker = monitor.get_health_checker()

        baselines = await health_checker.collector.get_performance_baselines()
        assert len(baselines) > 0

        baseline_names = list(map(lambda b: b.metric_name, baselines))
        assert "query_execution_time" in baseline_names
        assert "connection_pool_utilization" in baseline_names


class TestMonitoringIntegration:
    """Test comprehensive monitoring integration."""

    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self):
        collector = InMemoryDbMetricsCollector()
        monitor = DatabaseMonitor(collector)

        query_monitor = monitor.get_query_monitor()
        async with query_monitor.monitor_query(
            query="SELECT * FROM users WHERE id = ?",
            parameters=[123],
            connection_id="conn_1",
        ):
            await asyncio.sleep(0.01)

        txn_monitor = monitor.get_transaction_monitor()
        async with txn_monitor.monitor_transaction("txn_1"):
            await asyncio.sleep(0.01)

        stats = await monitor.get_stats()

        query_stats = stats["query_stats"]
        assert query_stats["total_queries"] == 1
        assert query_stats["successful_queries"] == 1
        assert query_stats["failed_queries"] == 0

        txn_stats = stats["transaction_stats"]
        assert txn_stats["total_transactions"] == 1
        assert txn_stats["successful_transactions"] == 1
        assert txn_stats["failed_transactions"] == 0
        assert txn_stats["commit_count"] == 1
        assert txn_stats["rollback_count"] == 0

    @pytest.mark.asyncio
    async def test_health_check_workflow(self, tmp_path):
        collector = InMemoryDbMetricsCollector()
        monitor = DatabaseMonitor(collector)

        # tmp_path-backed file: a bare test.db resolves against the process
        # CWD and leaks a stray file at the package root.
        health_result = await monitor.perform_health_check(
            f"sqlite:///{tmp_path / 'health.db'}"
        )

        assert "overall_status" in health_result
        assert "checks" in health_result
        assert "timestamp" in health_result
        assert isinstance(health_result["checks"], list)

        checks = health_result["checks"]
        assert len(checks) >= 1

        db_check = next((c for c in checks if c["component"] == "database"), None)
        assert db_check is not None
        assert "status" in db_check
        assert "message" in db_check

    @pytest.mark.asyncio
    async def test_monitor_with_custom_collector(self):
        collector = InMemoryDbMetricsCollector(max_metrics=5)
        monitor = DatabaseMonitor(collector)

        for i in range(10):
            metrics = QueryMetrics(
                query=f"SELECT {i}",
                parameters=None,
                execution_time=0.1,
                timestamp=datetime.now(UTC),
                success=True,
                connection_id=f"conn_{i}",
            )
            await collector.record_query_metrics(metrics)

        assert len(collector.query_metrics) == 5

        stats = await monitor.get_stats()
        assert stats["query_stats"]["total_queries"] == 5
