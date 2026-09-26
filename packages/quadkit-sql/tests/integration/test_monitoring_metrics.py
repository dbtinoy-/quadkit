"""Metrics collection and data structure tests for database monitoring."""

from datetime import UTC, datetime

import pytest

from quadkit.sql.monitoring import (
    ConnectionMetrics,
    InMemoryDbMetricsCollector,
    PerformanceBaseline,
    QueryMetrics,
    TransactionMetrics,
)


class TestInMemoryDbMetricsCollector:
    """Test InMemoryDbMetricsCollector functionality."""

    @pytest.fixture
    def collector(self):
        return InMemoryDbMetricsCollector()

    @pytest.mark.asyncio
    async def test_collector_creation(self, collector):
        assert collector is not None
        assert hasattr(collector, "record_query_metrics")
        assert hasattr(collector, "record_connection_metrics")
        assert hasattr(collector, "record_transaction_metrics")

    @pytest.mark.asyncio
    async def test_query_metrics_collection(self, collector):
        metrics = QueryMetrics(
            query="SELECT * FROM test",
            parameters=["param1"],
            execution_time=0.1,
            timestamp=datetime.now(UTC),
            success=True,
            connection_id="test_conn",
        )

        await collector.record_query_metrics(metrics)

        assert len(collector.query_metrics) == 1
        recorded = collector.query_metrics[0]
        assert recorded.query == "SELECT * FROM test"
        assert recorded.success is True
        assert recorded.execution_time == 0.1

    @pytest.mark.asyncio
    async def test_connection_metrics_collection(self, collector):
        metrics = ConnectionMetrics(
            active_connections=5,
            total_connections=10,
            available_connections=5,
            checked_out_connections=5,
            checked_in_connections=5,
            utilization=0.5,
            timestamp=datetime.now(UTC),
        )

        await collector.record_connection_metrics(metrics)

        assert len(collector.connection_metrics) == 1
        recorded = collector.connection_metrics[0]
        assert recorded.active_connections == 5
        assert recorded.total_connections == 10
        assert recorded.utilization == 0.5

    @pytest.mark.asyncio
    async def test_transaction_metrics_collection(self, collector):
        start_time = datetime.now(UTC)
        end_time = datetime.now(UTC)

        metrics = TransactionMetrics(
            transaction_id="test_txn",
            start_time=start_time,
            end_time=end_time,
            duration=0.2,
            operation="commit",
            success=True,
            deadlock_detected=False,
        )

        await collector.record_transaction_metrics(metrics)

        assert len(collector.transaction_metrics) == 1
        recorded = collector.transaction_metrics[0]
        assert recorded.transaction_id == "test_txn"
        assert recorded.operation == "commit"
        assert recorded.success is True
        assert recorded.deadlock_detected is False

    @pytest.mark.asyncio
    async def test_get_query_stats(self, collector):
        base_time = datetime.now(UTC)
        metrics = [
            QueryMetrics(
                "SELECT * FROM users", None, 0.1, base_time, True, None, "conn1",
            ),
            QueryMetrics(
                "INSERT INTO users", ["john"], 0.05, base_time, True, None, "conn1",
            ),
            QueryMetrics(
                "SELECT * FROM posts", None, 2.0, base_time, False, "timeout", "conn2",
            ),
        ]

        for metric in metrics:
            await collector.record_query_metrics(metric)

        stats = await collector.get_query_stats()

        assert stats["total_queries"] == 3
        assert stats["successful_queries"] == 2
        assert stats["failed_queries"] == 1
        assert stats["average_execution_time"] > 0
        assert "SELECT" in stats["query_count_by_type"]
        assert "INSERT" in stats["query_count_by_type"]

    @pytest.mark.asyncio
    async def test_get_transaction_stats(self, collector):
        base_time = datetime.now(UTC)
        metrics = [
            TransactionMetrics(
                "txn1", base_time, base_time, 0.1, "commit", True, False,
            ),
            TransactionMetrics(
                "txn2", base_time, base_time, 0.2, "rollback", False, True,
            ),
            TransactionMetrics(
                "txn3", base_time, base_time, 0.15, "commit", True, False,
            ),
        ]

        for metric in metrics:
            await collector.record_transaction_metrics(metric)

        stats = await collector.get_transaction_stats()

        assert stats["total_transactions"] == 3
        assert stats["successful_transactions"] == 2
        assert stats["failed_transactions"] == 1
        assert stats["commit_count"] == 2
        assert stats["rollback_count"] == 1
        assert stats["deadlock_count"] == 1
        assert stats["commit_ratio"] == 2 / 3

    @pytest.mark.asyncio
    async def test_get_connection_stats(self, collector):
        base_time = datetime.now(UTC)
        metrics = [
            ConnectionMetrics(5, 10, 5, 5, 5, 0.5, base_time),
            ConnectionMetrics(7, 10, 3, 7, 3, 0.7, base_time),
            ConnectionMetrics(3, 10, 7, 3, 7, 0.3, base_time),
        ]

        for metric in metrics:
            await collector.record_connection_metrics(metric)

        stats = await collector.get_connection_stats()

        assert stats["total_samples"] == 3
        assert stats["average_active_connections"] == 5.0
        assert stats["average_utilization"] == 0.5
        assert stats["max_utilization"] == 0.7
        assert stats["min_utilization"] == 0.3
        assert stats["current_active_connections"] == 3
        assert stats["current_total_connections"] == 10
        assert stats["current_utilization"] == 0.3

    @pytest.mark.asyncio
    async def test_performance_baselines(self, collector):
        baselines = await collector.get_performance_baselines()
        assert len(baselines) > 0

        baseline_names = list(map(lambda b: b.metric_name, baselines))
        assert "query_execution_time" in baseline_names
        assert "connection_pool_utilization" in baseline_names
        assert "transaction_commit_ratio" in baseline_names

        custom_baseline = PerformanceBaseline(
            metric_name="custom_metric",
            expected_value=1.0,
            warning_threshold=2.0,
            critical_threshold=5.0,
            unit="requests/sec",
            description="Custom performance metric",
        )

        await collector.set_performance_baseline(custom_baseline)

        updated_baselines = await collector.get_performance_baselines()
        assert len(updated_baselines) == len(baselines) + 1

        custom_found = next(
            (b for b in updated_baselines if b.metric_name == "custom_metric"), None,
        )
        assert custom_found is not None
        assert custom_found.expected_value == 1.0


class TestMetricsDataStructures:
    """Test metrics data structure creation."""

    def test_query_metrics_creation(self):
        timestamp = datetime.now(UTC)
        metrics = QueryMetrics(
            query="SELECT * FROM test",
            parameters=["param1", "param2"],
            execution_time=0.123,
            timestamp=timestamp,
            success=True,
            connection_id="test_conn_123",
        )

        assert metrics.query == "SELECT * FROM test"
        assert metrics.parameters == ["param1", "param2"]
        assert metrics.execution_time == 0.123
        assert metrics.timestamp == timestamp
        assert metrics.success is True
        assert metrics.connection_id == "test_conn_123"
        assert metrics.error_message is None
        assert metrics.transaction_id is None

    def test_connection_metrics_creation(self):
        timestamp = datetime.now(UTC)
        metrics = ConnectionMetrics(
            active_connections=5,
            total_connections=10,
            available_connections=5,
            checked_out_connections=5,
            checked_in_connections=5,
            utilization=0.5,
            timestamp=timestamp,
        )

        assert metrics.active_connections == 5
        assert metrics.total_connections == 10
        assert metrics.available_connections == 5
        assert metrics.checked_out_connections == 5
        assert metrics.checked_in_connections == 5
        assert metrics.utilization == 0.5
        assert metrics.timestamp == timestamp

    def test_transaction_metrics_creation(self):
        start_time = datetime.now(UTC)
        end_time = datetime.now(UTC)

        metrics = TransactionMetrics(
            transaction_id="txn_123",
            start_time=start_time,
            end_time=end_time,
            duration=0.234,
            operation="commit",
            success=True,
            deadlock_detected=False,
        )

        assert metrics.transaction_id == "txn_123"
        assert metrics.start_time == start_time
        assert metrics.end_time == end_time
        assert metrics.duration == 0.234
        assert metrics.operation == "commit"
        assert metrics.success is True
        assert metrics.deadlock_detected is False
        assert metrics.error_message is None
        assert metrics.nested_level == 0
