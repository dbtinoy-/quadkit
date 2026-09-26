import pytest

from quadkit.sql.monitoring.database_monitor import (
    DatabaseHealthChecker,
)
from quadkit.sql.monitoring.metrics import InMemoryDbMetricsCollector


@pytest.mark.asyncio
async def test_check_connection_pool_health_logs_exception(capsys):
    checker = DatabaseHealthChecker(InMemoryDbMetricsCollector())

    class BadPool:
        @property
        def _active_connections(self):
            raise RuntimeError("boom")

        @property
        def _total_connections(self):
            raise RuntimeError("boom")

    res = await checker.check_connection_pool_health(BadPool())

    assert res.status == "critical"
    assert "Connection pool health check failed" in capsys.readouterr().out
