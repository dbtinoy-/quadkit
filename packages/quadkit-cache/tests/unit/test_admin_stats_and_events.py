"""Focused tests for cache domain events and the admin stats page."""

from __future__ import annotations

from typing import Any

from quadkit.cache.admin.pages.stats import CacheStatsPage
from quadkit.cache.events import (
    CacheConnectedEvent,
    CacheEvictedEvent,
    CacheHitEvent,
    CacheMissEvent,
)
from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import EmptyContent, Stat, StatContent
from quadkit.contracts.core.health import (
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.domain.events import DomainEvent


class _FakeCache:
    def __init__(self, health: HealthCheckResult | Exception) -> None:
        self._health = health

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        if isinstance(self._health, Exception):
            raise self._health
        return self._health


class TestCacheEvents:
    def test_cache_hit_event(self) -> None:
        event = CacheHitEvent(key="k", backend="memory")
        assert isinstance(event, DomainEvent)
        assert event.key == "k"
        assert event.backend == "memory"

    def test_cache_miss_event(self) -> None:
        event = CacheMissEvent(key="k", backend="memory")
        assert event.key == "k"

    def test_cache_evicted_event(self) -> None:
        event = CacheEvictedEvent(key="k", backend="memory", reason="ttl")
        assert event.reason == "ttl"

    def test_cache_connected_event(self) -> None:
        event = CacheConnectedEvent(backend="redis", host="h")
        assert event.host == "h"


class TestCacheStatsPage:
    def _healthy(self, **details: Any) -> HealthCheckResult:
        return HealthCheckResult(
            component="cache",
            status=HealthStatus.HEALTHY,
            duration_ms=12.5,
            details=details,
        )

    def _stat(self, content: PageContent, label: str) -> Stat:
        assert isinstance(content.body, StatContent)
        for stat in content.body.stats:
            if stat.label == label:
                return stat
        raise AssertionError(f"stat {label!r} not found")

    def test_no_cache_returns_unavailable(self) -> None:
        import asyncio

        content = asyncio.run(CacheStatsPage(cache=None).handle(object()))
        assert content.title == "Cache Statistics"
        assert isinstance(content.body, EmptyContent)
        assert content.body.title == "Cache Unavailable"
        assert content.body.message == "The cache backend could not be resolved."
        assert content.body.icon == "database"

    def test_healthy_with_numeric_metrics(self) -> None:
        import asyncio

        cache = _FakeCache(
            self._healthy(
                metrics={
                    "hit_rate": 0.8,
                    "total_operations": 10,
                    "hits": 8,
                    "misses": 2,
                    "sets": 1,
                    "deletes": 0,
                    "errors": 0,
                    "avg_latency_ms": 3.2,
                }
            )
        )
        content = asyncio.run(CacheStatsPage(cache=cache).handle(object()))
        assert content.title == "Cache Statistics"
        assert self._stat(content, "Backend").value == "OK"
        assert self._stat(content, "Hit Ratio").value == "80%"
        assert self._stat(content, "Operations").value == "10"
        assert self._stat(content, "Avg Latency").value == "3.2ms"

    def test_healthy_with_string_metrics(self) -> None:
        import asyncio

        cache = _FakeCache(
            self._healthy(metrics={"hit_rate": "N/A", "avg_latency_ms": "unknown"})
        )
        content = asyncio.run(CacheStatsPage(cache=cache).handle(object()))
        assert self._stat(content, "Hit Ratio").value == "N/A"
        assert self._stat(content, "Avg Latency").value == "unknown"

    def test_health_check_raises_marks_down(self) -> None:
        import asyncio

        cache = _FakeCache(RuntimeError("boom"))
        content = asyncio.run(CacheStatsPage(cache=cache).handle(object()))
        assert self._stat(content, "Backend").value == "Down"
