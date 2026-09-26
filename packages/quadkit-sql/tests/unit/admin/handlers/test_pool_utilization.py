"""Tests for the pool_utilization admin widget handler."""

from __future__ import annotations

from quadkit.contracts.admin import WidgetParams
from quadkit.result import Ok
from quadkit.sql.admin.handlers.pool_utilization import PoolUtilizationWidgetHandler


class _FakePool:
    def __init__(self, stats: dict) -> None:
        self._stats = stats

    async def get_pool_stats(self) -> dict:
        return self._stats


class _FakeDatabaseProvider:
    def __init__(self, pool: _FakePool | None = None) -> None:
        self._pool = pool

    async def get_primary_pool(self) -> _FakePool:
        if self._pool is None:
            raise RuntimeError("no pool")
        return self._pool


async def test_pool_utilization_reports_real_stats() -> None:
    pool = _FakePool(
        {
            "active_connections": 7,
            "max_connections": 20,
            "utilization_rate": 0.35,
        }
    )
    handler = PoolUtilizationWidgetHandler(_FakeDatabaseProvider(pool))
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    content = result.unwrap()
    labels = [s.label for s in content.stats]
    values = [s.value for s in content.stats]
    assert "Active Connections" in labels
    assert "7/20" in values
    assert "Utilization" in labels
    assert "35.0%" in values


async def test_pool_utilization_degrades_without_pool() -> None:
    handler = PoolUtilizationWidgetHandler(_FakeDatabaseProvider(None))
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "Unavailable" in values


__all__ = [
    "test_pool_utilization_reports_real_stats",
    "test_pool_utilization_degrades_without_pool",
]
