"""Unit tests for quadkit.cache.types module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.cache.types import (
    BackendType,
    CacheEntry,
    CacheHealthResult,
    CacheItem,
    CacheMetrics,
    CacheResult,
    CacheStats,
    CacheStatus,
    CacheStatusHandler,
    DistributedLockInfo,
    TaggedCacheKey,
    T,
)


class TestBackendType:
    def test_values(self) -> None:
        assert BackendType.MEMORY.value == "memory"
        assert BackendType.REDIS.value == "redis"
        assert BackendType.MEMCACHED.value == "memcached"

    def test_members(self) -> None:
        members = list(BackendType)
        assert len(members) == 3
        assert BackendType.MEMORY in members
        assert BackendType.REDIS in members
        assert BackendType.MEMCACHED in members


class TestCacheStatus:
    def test_values(self) -> None:
        assert CacheStatus.HIT.value == "hit"
        assert CacheStatus.MISS.value == "miss"
        assert CacheStatus.SET.value == "set"
        assert CacheStatus.DELETE.value == "delete"
        assert CacheStatus.ERROR.value == "error"
        assert CacheStatus.EXPIRED.value == "expired"
        assert CacheStatus.STALE.value == "stale"

    def test_members(self) -> None:
        members = list(CacheStatus)
        assert len(members) == 7


class TestCacheItem:
    @pytest.fixture
    def item(self) -> CacheItem:
        return CacheItem(key="test:key", value="test_value", ttl=60)

    def test_init(self, item: CacheItem) -> None:
        assert item.key == "test:key"
        assert item.value == "test_value"
        assert item.ttl == 60
        assert item.access_count == 0
        assert item.tags == []
        assert item.version is None

    def test_is_expired_with_ttl(self, item: CacheItem) -> None:
        item_ttl = CacheItem(key="test:key", value="test", ttl=1)
        item_ttl.created_at = datetime.now(UTC) - timedelta(seconds=10)
        assert item_ttl.is_expired is True

    def test_is_expired_no_ttl(self, item: CacheItem) -> None:
        assert item.is_expired is False

    def test_is_expired_none_ttl(self) -> None:
        item = CacheItem(key="test", value="test", ttl=None)
        assert item.is_expired is False

    def test_expires_at_with_ttl(self, item: CacheItem) -> None:
        expires = item.expires_at
        assert expires is not None
        assert expires.tzinfo is not None

    def test_expires_at_no_ttl(self, item: CacheItem) -> None:
        item_none_ttl = CacheItem(key=item.key, value=item.value, ttl=None)
        assert item_none_ttl.expires_at is None

    def test_touch(self, item: CacheItem) -> None:
        original_count = item.access_count
        item.touch()
        assert item.access_count == original_count + 1
        assert item.accessed_at is not None


class TestCacheResult:
    @pytest.fixture
    def result(self) -> CacheResult[str]:
        return CacheResult(CacheStatus.HIT, "test_value", "test:key", 1.5, "memory")

    def test_init(self, result: CacheResult[str]) -> None:
        assert result.status == CacheStatus.HIT
        assert result.value == "test_value"
        assert result.key == "test:key"
        assert result.latency_ms == 1.5
        assert result.from_backend == "memory"

    def test_is_hit_true(self, result: CacheResult[str]) -> None:
        assert result.is_hit is True

    def test_is_hit_false(self) -> None:
        result = CacheResult(CacheStatus.MISS, None, "test:key")
        assert result.is_hit is False

    def test_is_miss_true(self) -> None:
        result = CacheResult(CacheStatus.MISS, None, "test:key")
        assert result.is_miss is True

    def test_is_miss_false(self, result: CacheResult[str]) -> None:
        assert result.is_miss is False

    def test_hit_classmethod(self) -> None:
        result = CacheResult.hit(value="test", key="test:key", latency=1.0, backend="redis")
        assert result.status == CacheStatus.HIT
        assert result.value == "test"
        assert result.key == "test:key"
        assert result.latency_ms == 1.0
        assert result.from_backend == "redis"

    def test_miss_classmethod(self) -> None:
        result = CacheResult.miss(key="test:key", latency=0.5)
        assert result.status == CacheStatus.MISS
        assert result.value is None
        assert result.key == "test:key"
        assert result.latency_ms == 0.5


class TestCacheMetrics:
    @pytest.fixture
    def metrics(self) -> CacheMetrics:
        return CacheMetrics()

    def test_init_defaults(self, metrics: CacheMetrics) -> None:
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.sets == 0
        assert metrics.deletes == 0
        assert metrics.errors == 0
        assert metrics.total_latency_ms == 0.0
        assert metrics.operation_count == 0

    def test_hit_rate_empty(self, metrics: CacheMetrics) -> None:
        assert metrics.hit_rate == 0.0

    def test_hit_rate_with_hits(self, metrics: CacheMetrics) -> None:
        metrics.hits = 80
        metrics.misses = 20
        assert metrics.hit_rate == 0.8

    def test_hit_rate_no_misses(self, metrics: CacheMetrics) -> None:
        metrics.hits = 100
        assert metrics.hit_rate == 1.0


class TestCacheStats:
    @pytest.fixture
    def stats(self) -> CacheStats:
        return CacheStats(
            total_keys=100,
            memory_usage_bytes=1024,
            backends={"memory": {"keys": 100}},
        )

    def test_init(self, stats: CacheStats) -> None:
        assert stats.total_keys == 100
        assert stats.memory_usage_bytes == 1024

    def test_to_dict(self, stats: CacheStats) -> None:
        result = stats.to_dict()
        assert "total_keys" in result
        assert "memory_usage_bytes" in result


class TestCacheHealthResult:
    @pytest.fixture
    def health_result(self) -> CacheHealthResult:
        return CacheHealthResult(
            status=HealthStatus.HEALTHY,
            message="OK",
            latency_ms=1.0,
        )

    def test_is_healthy_true(self) -> None:
        result = CacheHealthResult(status=HealthStatus.HEALTHY)
        assert result.is_healthy is True

    def test_is_healthy_false(self) -> None:
        result = CacheHealthResult(status=HealthStatus.UNHEALTHY)
        assert result.is_healthy is False

    def test_to_dict(self) -> None:
        result = CacheHealthResult(status=HealthStatus.HEALTHY, message="test")
        d = result.to_dict()
        assert "status" in d


class TestTaggedCacheKey:
    def test_init_empty_tags(self) -> None:
        key = TaggedCacheKey(key="test:key")
        assert key.tags == []

    def test_init_with_tags(self) -> None:
        key = TaggedCacheKey(key="test:key", tags=["tag1", "tag2"])
        assert len(key.tags) == 2


class TestDistributedLockInfo:
    def test_init(self) -> None:
        now = datetime.now(UTC)
        info = DistributedLockInfo(
            key="lock:test",
            owner="worker-1",
            acquired_at=now,
            ttl=30,
        )
        assert info.key == "lock:test"
        assert info.owner == "worker-1"
        assert info.ttl == 30


class TestCacheEntry:
    @pytest.fixture
    def entry(self) -> CacheEntry[str]:
        now = datetime.now(UTC)
        return CacheEntry(
            value="test_value",
            cached_at=now,
            expires_at=now + timedelta(seconds=60),
        )

    def test_init(self, entry: CacheEntry[str]) -> None:
        assert entry.value == "test_value"

    def test_is_expired_false(self, entry: CacheEntry[str]) -> None:
        assert entry.is_expired is False

    def test_is_expired_true(self) -> None:
        now = datetime.now(UTC)
        entry = CacheEntry(
            value="expired",
            cached_at=now - timedelta(seconds=120),
            expires_at=now - timedelta(seconds=60),
        )
        assert entry.is_expired is True


class TestCacheStatusHandlerProtocol:
    def test_protocol_exists(self) -> None:
        assert CacheStatusHandler is not None