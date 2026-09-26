"""
Write-through caching strategy for Quadkit Cache.

Provides automated cache updates on database writes to ensure
data consistency and high performance.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, Generic, TypeVar, cast

from quadkit.cache.service.core import CacheService
from quadkit.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class WriteThroughCache(Generic[T]):
    """
    Write-through caching strategy.

    Ensures that whenever data is written to the primary store (e.g., DB),
    it is also updated in the cache.
    """

    def __init__(
        self,
        cache_service: CacheService,
        namespace: str,
        ttl: int | None = None,
        key_field: str = "id",
    ):
        self.cache_service = cache_service
        self.namespace = namespace
        self.ttl = ttl
        self.key_field = key_field

    def _make_key(self, entity_id: Any) -> str:
        return f"{self.namespace}:{entity_id}"

    async def get(self, entity_id: Any, loader: Callable[[], Any]) -> T:
        """Get from cache, or load and fill cache (Read-through)"""
        key = self._make_key(entity_id)
        cached = await self.cache_service.get(key)
        if cached is not None:
            return cast("T", cached)

        # Load from primary store
        data = await loader()
        if data is not None:
            await self.cache_service.set(key, data, self.ttl)
        return cast("T", data)

    async def update(self, entity_id: Any, data: T, writer: Callable[[T], Any]) -> T:
        """Update cache after writing to primary store (Write-through)"""
        # Write to primary store first
        result = await writer(data)

        # Update cache
        key = self._make_key(entity_id)
        await self.cache_service.set(key, data, self.ttl)

        return cast("T", result)

    async def delete(self, entity_id: Any, deleter: Callable[[], Any]) -> bool:
        """Remove from cache after removing from primary store"""
        # Remove from primary store
        result = await deleter()

        # Invalidate cache
        key = self._make_key(entity_id)
        await self.cache_service.delete(key)

        return cast("bool", result)

    async def shutdown(self) -> None:
        """Flush any pending state and release resources.

        ``WriteThroughCache`` writes through synchronously — every ``update()``
        call already persists to both the primary store and the cache before
        returning.  ``shutdown()`` is therefore a no-op for this strategy but
        is provided so callers can use a uniform lifecycle interface across
        different caching strategies.
        """
        logger.debug("WriteThroughCache.shutdown(): all writes already flushed")


def write_through(
    cache_service: CacheService,
    namespace: str,
    ttl: int | None = None,
    key_field: str = "id",
) -> Callable[[F], F]:
    """
    Decorator for repository methods to implement write-through caching.

    Usage:
        @write_through(cache_service, "users")
        async def update_user(self, user):
            ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # This is a simplified decorator.
            # In a real implementation, we'd need to extract the entity and its ID
            # from the arguments.
            return await func(*args, **kwargs)

            # Extract ID and data for caching
            # (In practice, this would use introspection)

        return cast("F", wrapper)

    return decorator
