"""Unit tests for the LRU StatementCache (performance/statement_cache.py)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.sql.performance.statement_cache import StatementCache


class _Provider:
    def __init__(self) -> None:
        self.prepared: list[str] = []

    async def prepare(self, sql: str) -> str:
        self.prepared.append(sql)
        return f"prepared:{sql}"


class _NoPrepareProvider:
    pass


class TestStatementCache:
    @pytest.mark.asyncio
    async def test_miss_prepares_and_caches(self) -> None:
        cache = StatementCache()
        provider = _Provider()
        first = await cache.get_or_prepare("SELECT 1", provider)
        assert first == "prepared:SELECT 1"
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert (stats["hits"], stats["misses"]) == (0, 1)

    @pytest.mark.asyncio
    async def test_hit_reuses_prepared_statement(self) -> None:
        cache = StatementCache()
        provider = _Provider()
        await cache.get_or_prepare("SELECT 1", provider)
        second = await cache.get_or_prepare("SELECT 1", provider)
        assert second == "prepared:SELECT 1"
        assert provider.prepared == ["SELECT 1"]  # prepared exactly once
        stats = cache.get_stats()
        assert (stats["hits"], stats["misses"]) == (1, 1)

    @pytest.mark.asyncio
    async def test_provider_without_prepare_falls_back_to_raw_sql(self) -> None:
        cache = StatementCache()
        result = await cache.get_or_prepare("SELECT 2", _NoPrepareProvider())
        assert result == "SELECT 2"

    @pytest.mark.asyncio
    async def test_lru_eviction_at_capacity(self) -> None:
        cache = StatementCache(max_size=2)
        provider = _Provider()
        await cache.get_or_prepare("q1", provider)
        await cache.get_or_prepare("q2", provider)
        # Touch q1 so q2 becomes the LRU entry, then fill capacity with q3.
        await cache.get_or_prepare("q1", provider)  # hit, refreshes q1
        await cache.get_or_prepare("q3", provider)  # evicts q2
        assert cache.get_stats()["size"] == 2
        # q1 survived the eviction (no re-prepare).
        before = len(provider.prepared)
        await cache.get_or_prepare("q1", provider)
        assert len(provider.prepared) == before
        # q2 was evicted: re-accessing it prepares again.
        before = len(provider.prepared)
        await cache.get_or_prepare("q2", provider)
        assert len(provider.prepared) == before + 1

    @pytest.mark.asyncio
    async def test_invalidate_single_statement(self) -> None:
        cache = StatementCache()
        provider = _Provider()
        await cache.get_or_prepare("q1", provider)
        await cache.get_or_prepare("q2", provider)
        cache.invalidate("q1")
        stats = cache.get_stats()
        assert stats["size"] == 1
        before = len(provider.prepared)
        await cache.get_or_prepare("q1", provider)
        assert len(provider.prepared) == before + 1
        # Invalidating an absent statement is a no-op.
        cache.invalidate("absent")

    @pytest.mark.asyncio
    async def test_invalidate_all_clears_entries_but_keeps_stats(self) -> None:
        cache = StatementCache()
        await cache.get_or_prepare("q1", _Provider())
        await cache.get_or_prepare("q2", _Provider())
        cache.invalidate_all()
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["misses"] == 2  # stats are not reset by invalidate_all

    def test_clear_resets_stats(self) -> None:
        cache = StatementCache()
        cache.invalidate_all()
        cache.clear()
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert (stats["hits"], stats["misses"], stats["hit_rate"]) == (0, 0, 0.0)
        assert stats["top_queries"] == []

    @pytest.mark.asyncio
    async def test_hit_rate_and_top_queries(self) -> None:
        cache = StatementCache(max_size=7)
        provider = _Provider()
        stats = cache.get_stats()
        assert stats["hit_rate"] == 0.0  # no lookups yet
        assert stats["top_queries"] == []

        await cache.get_or_prepare("q", provider)
        await cache.get_or_prepare("q", provider)
        await cache.get_or_prepare("other", provider)
        stats = cache.get_stats()
        assert set(stats) == {
            "size",
            "max_size",
            "hits",
            "misses",
            "hit_rate",
            "top_queries",
        }
        assert stats["hit_rate"] == round(1 / 3, 3)
        # Top queries sorted by hit count, SQL truncated to 80 chars.
        assert stats["top_queries"][0] == {"sql": "q", "hits": 1}
