"""Cache status handler registry for metrics collection."""

from __future__ import annotations

from quadkit.cache.types import CacheMetrics, CacheStatus, CacheStatusHandler


class HitStatusHandler:
    """Handler for HIT cache status."""

    def can_handle(self, status: CacheStatus) -> bool:
        return status == CacheStatus.HIT

    async def record(self, metrics: CacheMetrics, count: int) -> None:
        metrics.hits += count


class MissStatusHandler:
    """Handler for MISS cache status."""

    def can_handle(self, status: CacheStatus) -> bool:
        return status == CacheStatus.MISS

    async def record(self, metrics: CacheMetrics, count: int) -> None:
        metrics.misses += count


class SetStatusHandler:
    """Handler for SET cache status."""

    def can_handle(self, status: CacheStatus) -> bool:
        return status == CacheStatus.SET

    async def record(self, metrics: CacheMetrics, count: int) -> None:
        metrics.sets += count


class DeleteStatusHandler:
    """Handler for DELETE cache status."""

    def can_handle(self, status: CacheStatus) -> bool:
        return status == CacheStatus.DELETE

    async def record(self, metrics: CacheMetrics, count: int) -> None:
        metrics.deletes += count


class ErrorStatusHandler:
    """Handler for ERROR cache status."""

    def can_handle(self, status: CacheStatus) -> bool:
        return status == CacheStatus.ERROR

    async def record(self, metrics: CacheMetrics, count: int) -> None:
        metrics.errors += count


class CacheStatusRegistry:
    """Registry for cache status handlers.

    Routes cache status events to appropriate handlers for metrics collection.
    """

    def __init__(self) -> None:
        """Initialize the registry with default handlers."""
        self._handlers: list[CacheStatusHandler] = [
            HitStatusHandler(),
            MissStatusHandler(),
            SetStatusHandler(),
            DeleteStatusHandler(),
            ErrorStatusHandler(),
        ]

    def register(self, handler: CacheStatusHandler) -> None:
        """Register a new status handler.

        Args:
            handler: The handler to register.
        """
        self._handlers.append(handler)

    async def record(
        self,
        status: CacheStatus,
        metrics: CacheMetrics,
        count: int = 1,
    ) -> None:
        """Record a cache status event.

        Args:
            status: The cache status.
            metrics: The metrics object to update.
            count: The number of operations.
        """
        for handler in self._handlers:
            if handler.can_handle(status):
                await handler.record(metrics, count)


# Global registry instance
_registry: CacheStatusRegistry | None = None


def get_cache_status_registry() -> CacheStatusRegistry:
    """Get the global cache status registry.

    Returns:
        The global registry instance.
    """
    global _registry
    if _registry is None:
        _registry = CacheStatusRegistry()
    return _registry


def reset_cache_status_registry() -> None:
    """Reset the global cache status registry.

    Useful for testing.
    """
    global _registry
    _registry = None


__all__ = [
    "CacheStatusRegistry",
    "DeleteStatusHandler",
    "ErrorStatusHandler",
    "HitStatusHandler",
    "MissStatusHandler",
    "SetStatusHandler",
    "get_cache_status_registry",
    "reset_cache_status_registry",
]
