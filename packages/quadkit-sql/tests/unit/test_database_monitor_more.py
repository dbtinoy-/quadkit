import pytest

from quadkit.sql.monitoring import (
    ConnectionPoolMonitor,
    DatabaseHealthChecker,
    DatabaseMonitor,
    QueryMonitor,
    TransactionMonitor,
)
from quadkit.sql.monitoring.metrics import InMemoryDbMetricsCollector


@pytest.mark.asyncio
async def test_query_monitor_success_and_failure():
    collector = InMemoryDbMetricsCollector()
    monitor = QueryMonitor(collector, slow_query_threshold=0.0)

    # Successful query
    async with monitor.monitor_query("SELECT 1", parameters=[1], connection_id="c1"):
        pass

    stats = await monitor.get_stats()
    assert stats["total_queries"] == 1
    assert stats["successful_queries"] == 1

    # Failed query (raises inside context manager)
    with pytest.raises(RuntimeError):
        async with monitor.monitor_query(
            "SELECT X", parameters=None, connection_id="c2",
        ):
            raise RuntimeError("boom")

    stats = await monitor.get_stats()
    assert stats["total_queries"] == 2
    assert stats["failed_queries"] == 1


@pytest.mark.asyncio
async def test_transaction_monitor_commit_and_rollback_and_deadlock_detection():
    collector = InMemoryDbMetricsCollector()
    monitor = TransactionMonitor(collector)

    # Commit case
    async with monitor.monitor_transaction("tx1"):
        pass

    tx_stats = await collector.get_transaction_stats()
    assert tx_stats["total_transactions"] >= 1
    assert tx_stats["successful_transactions"] >= 1
    assert tx_stats["commit_count"] >= 1

    # Rollback with deadlock in error message
    with pytest.raises(RuntimeError):
        async with monitor.monitor_transaction("tx_deadlock"):
            raise RuntimeError("deadlock detected during commit")

    tx_stats = await collector.get_transaction_stats()
    assert tx_stats["failed_transactions"] >= 1
    assert tx_stats["deadlock_count"] >= 1


@pytest.mark.asyncio
async def test_connection_pool_monitor_collects_metrics():
    collector = InMemoryDbMetricsCollector()
    monitor = ConnectionPoolMonitor(collector)

    class DummyPool:
        _active_connections = 3
        _total_connections = 10

    monitor.pool = DummyPool()

    await monitor._collect_pool_metrics()

    conn_stats = await collector.get_connection_stats()
    assert conn_stats["total_samples"] == 1
    assert conn_stats["current_active_connections"] == 3
    assert conn_stats["current_total_connections"] == 10


@pytest.mark.asyncio
async def test_health_checker_connection_pool_health():
    collector = InMemoryDbMetricsCollector()
    hc = DatabaseHealthChecker(collector)

    class PoolHealthy:
        _active_connections = 10
        _total_connections = 100

    class PoolWarning:
        _active_connections = 90
        _total_connections = 100

    class PoolCritical:
        _active_connections = 96
        _total_connections = 100

    healthy = await hc.check_connection_pool_health(PoolHealthy())
    assert healthy.status == "healthy"

    warning = await hc.check_connection_pool_health(PoolWarning())
    assert warning.status == "warning"

    critical = await hc.check_connection_pool_health(PoolCritical())
    assert critical.status == "critical"


@pytest.mark.asyncio
async def test_database_monitor_get_stats_integration():
    collector = InMemoryDbMetricsCollector()
    monitor = DatabaseMonitor(collector)

    # Record a query and a connection metric
    async with monitor.get_query_monitor().monitor_query("SELECT 1"):
        pass

    class DummyPool:
        _active_connections = 1
        _total_connections = 4

    await monitor.pool_monitor._collect_pool_metrics.__call__() if False else None
    # Use internal method to record connection metrics
    monitor.pool_monitor.pool = DummyPool()
    await monitor.pool_monitor._collect_pool_metrics()

    stats = await monitor.get_stats()
    assert "query_stats" in stats
    assert "connection_stats" in stats
    assert "transaction_stats" in stats
