"""Core type definitions for quadkit-cache.

This module provides shared data types, models, and enums used
throughout the caching system. Following the Root File Pattern,
types are defined at the package root for easy access.

Types:
    CacheItem: Represents a cached item with metadata
    CacheMetrics: Cache performance metrics
    CacheResult: Result of a cache operation
    CacheStats: Aggregated cache statistics
    BackendType: Enum of supported backend types
    DistributedLockInfo: Lock ownership information
    CacheEntry: Cache entry with metadata for stampede protection
    CacheStatusHandler: Protocol for cache status handlers
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, Generic, Protocol, TypeVar

from quadkit.contracts.core import HealthStatus

T = TypeVar("T")


class BackendType(StrEnum):
    """Supported cache backend types."""

    MEMORY = "memory"
    REDIS = "redis"
    MEMCACHED = "memcached"


class CacheStatus(StrEnum):
    """Status values for cache operations."""

    HIT = "hit"
    MISS = "miss"
    SET = "set"
    DELETE = "delete"
    ERROR = "error"
    EXPIRED = "expired"
    STALE = "stale"


@dataclass
class CacheItem:
    """Represents a cached item with metadata."""

    key: str
    value: Any
    ttl: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    accessed_at: datetime | None = None
    access_count: int = 0
    tags: list[str] = field(default_factory=list)
    version: str | None = None

    @property
    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        created = (
            self.created_at.replace(tzinfo=UTC)
            if self.created_at.tzinfo is None
            else self.created_at
        )
        return (datetime.now(UTC) - created).total_seconds() > self.ttl

    @property
    def expires_at(self) -> datetime | None:
        if self.ttl is None:
            return None
        created = (
            self.created_at.replace(tzinfo=UTC)
            if self.created_at.tzinfo is None
            else self.created_at
        )
        return created + timedelta(seconds=self.ttl)

    def touch(self) -> None:
        self.accessed_at = datetime.now(UTC)
        self.access_count += 1


@dataclass
class CacheResult(Generic[T]):
    """Result of a cache operation."""

    status: CacheStatus
    value: T | None = None
    key: str | None = None
    latency_ms: float | None = None
    from_backend: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_hit(self) -> bool:
        return self.status == CacheStatus.HIT

    @property
    def is_miss(self) -> bool:
        return self.status == CacheStatus.MISS

    @classmethod
    def hit(
        cls,
        value: T,
        key: str | None = None,
        latency: float | None = None,
        backend: str | None = None,
    ) -> CacheResult[T]:
        return cls(CacheStatus.HIT, value, key, latency, backend)

    @classmethod
    def miss(
        cls,
        key: str | None = None,
        latency: float | None = None,
    ) -> CacheResult[T]:
        return cls(CacheStatus.MISS, None, key, latency)


@dataclass
class CacheMetrics:
    """Cache performance metrics with atomic updates."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    operation_count: int = 0
    _lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    async def record(
        self,
        status: CacheStatus,
        latency: float = 0.0,
        count: int = 1,
    ) -> None:
        """Atomic record helper."""
        from quadkit.cache.service.registry import get_cache_status_registry

        async with self._lock:
            self.operation_count += count
            self.total_latency_ms += latency
            registry = get_cache_status_registry()
            await registry.record(status, self, count)

    async def record_hit(self, count: int = 1) -> None:
        """Convenience method to record hits."""
        await self.record(CacheStatus.HIT, count=count)

    async def record_miss(self, count: int = 1) -> None:
        """Convenience method to record misses."""
        await self.record(CacheStatus.MISS, count=count)

    async def record_set(self, count: int = 1) -> None:
        """Convenience method to record sets."""
        await self.record(CacheStatus.SET, count=count)

    async def record_delete(self, count: int = 1) -> None:
        """Convenience method to record deletes."""
        await self.record(CacheStatus.DELETE, count=count)

    async def record_error(self, count: int = 1) -> None:
        """Convenience method to record errors."""
        await self.record(CacheStatus.ERROR, count=count)

    def reset(self) -> None:
        """Reset counters while retaining the cache entries themselves."""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.errors = 0
        self.total_latency_ms = 0.0
        self.operation_count = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    async def to_dict(self) -> dict[str, Any]:
        async with self._lock:
            return {
                "hits": self.hits,
                "misses": self.misses,
                "sets": self.sets,
                "deletes": self.deletes,
                "errors": self.errors,
                "hit_rate": self.hit_rate,
                "total_operations": self.operation_count,
                "avg_latency_ms": self.total_latency_ms / self.operation_count
                if self.operation_count > 0
                else 0.0,
            }


@dataclass
class CacheStats:
    total_keys: int = 0
    memory_usage_bytes: int = 0
    backends: dict[str, dict[str, Any]] = field(default_factory=dict)
    metrics: CacheMetrics | None = None
    health_status: HealthStatus = HealthStatus.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_keys": self.total_keys,
            "memory_usage_bytes": self.memory_usage_bytes,
            "backends": self.backends,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "health_status": self.health_status.value,
        }


@dataclass
class CacheHealthResult:
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    backends: dict[str, dict[str, Any]] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        return vars(self)


@dataclass
class TaggedCacheKey:
    key: str
    tags: list[str] = field(default_factory=list)


@dataclass
class DistributedLockInfo:
    """Lock ownership information for distributed locks."""

    key: str
    owner: str
    acquired_at: datetime
    ttl: int
    renewal_task: asyncio.Task | None = None


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata for stampede protection.

    Attributes:
        value: Cached value.
        cached_at: When value was cached.
        expires_at: When value expires.
    """

    value: T
    cached_at: datetime
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return datetime.now(UTC) >= self.expires_at


class CacheStatusHandler(Protocol):
    """Protocol for cache status handlers.

    Implement this protocol to create custom handlers for cache
    status events. Handlers are registered with the cache status
    registry and called when corresponding cache operations occur.
    """

    def can_handle(self, status: CacheStatus) -> bool:
        """Check if this handler can handle the status.

        Args:
            status: The cache status to check.

        Returns:
            True if this handler can handle the status.
        """
        ...

    async def record(self, metrics: CacheMetrics, count: int) -> None:
        """Record metrics for the status.

        Args:
            metrics: The metrics object to update.
            count: The number of operations to record.
        """
        ...


__all__ = [
    "BackendType",
    "CacheEntry",
    "CacheHealthResult",
    "CacheItem",
    "CacheMetrics",
    "CacheResult",
    "CacheStats",
    "CacheStatus",
    "CacheStatusHandler",
    "DistributedLockInfo",
    "HealthStatus",
    "T",
    "TaggedCacheKey",
]
