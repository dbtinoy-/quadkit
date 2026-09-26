from datetime import UTC, datetime, timedelta

import pytest

from quadkit.sql.monitoring.metrics import (
    ConnectionMetrics,
    InMemoryDbMetricsCollector,
    PerformanceBaseline,
    QueryMetrics,
    TransactionMetrics,
)


@pytest.mark.asyncio
async def test_query_stats_empty_and_with_data():
    c = InMemoryDbMetricsCollector()

    empty = await c.get_query_stats()
    assert empty["total_queries"] == 0

    now = datetime.now(UTC)
    await c.record_query_metrics(QueryMetrics("SELECT 1", None, 0.1, now, True))
    await c.record_query_metrics(QueryMetrics("UPDATE t", None, 0.5, now, False, "err"))

    stats = await c.get_query_stats()
    assert stats["total_queries"] == 2
    assert stats["successful_queries"] == 1
    assert stats["failed_queries"] == 1
    assert stats["average_execution_time"] == pytest.approx((0.1 + 0.5) / 2)
    assert stats["slowest_query"]["execution_time"] == 0.5
    assert stats["query_count_by_type"]["SELECT"] == 1
    assert stats["query_count_by_type"]["UPDATE"] == 1


@pytest.mark.asyncio
async def test_transaction_and_connection_stats_and_baselines():
    c = InMemoryDbMetricsCollector()

    now = datetime.now(UTC)
    t1 = TransactionMetrics(
        "tx1",
        now - timedelta(seconds=5),
        now,
        5.0,
        "commit",
        True,
        False,
    )
    t2 = TransactionMetrics(
        "tx2",
        now - timedelta(seconds=10),
        now - timedelta(seconds=5),
        5.0,
        "rollback",
        False,
        True,
    )

    await c.record_transaction_metrics(t1)
    await c.record_transaction_metrics(t2)

    tstats = await c.get_transaction_stats()
    assert tstats["total_transactions"] == 2
    assert tstats["successful_transactions"] == 1
    assert tstats["failed_transactions"] == 1
    assert tstats["deadlock_count"] == 1
    assert tstats["commit_count"] == 1
    assert tstats["rollback_count"] == 1

    cm1 = ConnectionMetrics(2, 5, 3, 1, 4, 0.4, now)
    cm2 = ConnectionMetrics(4, 5, 1, 3, 2, 0.8, now)
    await c.record_connection_metrics(cm1)
    await c.record_connection_metrics(cm2)

    cstats = await c.get_connection_stats()
    assert cstats["total_samples"] == 2
    assert cstats["average_active_connections"] == pytest.approx((2 + 4) / 2)
    assert cstats["max_utilization"] == pytest.approx(0.8)
    assert cstats["current_active_connections"] == 4

    baselines = await c.get_performance_baselines()
    assert isinstance(baselines, list)

    new_baseline = PerformanceBaseline(
        "query_execution_time", 0.2, 0.6, 1.0, "s", "test",
    )
    await c.set_performance_baseline(new_baseline)
    bls = await c.get_performance_baselines()
    assert any(b.metric_name == "query_execution_time" for b in bls)
