"""Tests for the query_stats admin widget handler."""

from __future__ import annotations

from quadkit.contracts.admin import WidgetParams
from quadkit.result import Ok
from quadkit.sql.admin.handlers.query_stats import QueryStatsWidgetHandler


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


async def test_query_stats_reports_acquired_released() -> None:
    pool = _FakePool(
        {
            "acquired_connections": 10,
            "released_connections": 7,
        }
    )
    handler = QueryStatsWidgetHandler(_FakeDatabaseProvider(pool))
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    content = result.unwrap()
    labels = [s.label for s in content.stats]
    values = [s.value for s in content.stats]
    assert "Acquired" in labels
    assert "10" in values
    assert "Released" in labels
    assert "7" in values
    assert "In Progress" in labels
    assert "3" in values


async def test_query_stats_degrades_without_pool() -> None:
    handler = QueryStatsWidgetHandler(_FakeDatabaseProvider(None))
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "Unavailable" in values


__all__ = [
    "test_query_stats_reports_acquired_released",
    "test_query_stats_degrades_without_pool",
]
