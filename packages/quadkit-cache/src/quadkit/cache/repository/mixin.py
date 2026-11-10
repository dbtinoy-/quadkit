"""Read-through repository caching mixin with targeted key/pattern invalidation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

T = TypeVar("T")


class InvalidatingCacheMixin:
    """Mixin adding read-through caching and targeted invalidation to repositories.

    Subclasses set:
        _cache: ``CacheBackendProtocol`` or ``CacheProviderProtocol`` instance
        cache_prefix: Namespace key prefix (e.g. ``"pet"``, ``"breed"``)
        cache_ttl: Entry time-to-live in seconds
    """

    _cache: Any
    cache_prefix: str
    cache_ttl: int

    @property
    def cache(self) -> Any:
        """Return the underlying cache backend/provider."""
        return self._cache

    async def _cached_get(
        self,
        key: str,
        loader: Callable[[], Awaitable[T]],
    ) -> T:
        """Read-through lookup unwrapping ``Result``-returning backends transparently."""
        cache_key = f"{self.cache_prefix}:{key}"
        cached = await self._cache.get(cache_key)

        if hasattr(cached, "is_ok"):
            cached = cached.unwrap() if cached.is_ok() else None

        if cached is not None:
            return cached  # type: ignore[no-any-return]

        result = await loader()
        if result is not None:
            await self._cache.set(cache_key, result, ttl=self.cache_ttl)
        return result

    async def _invalidate(self, key: str) -> None:
        """Invalidate a single cached entry."""
        await self._cache.delete(f"{self.cache_prefix}:{key}")

    async def _invalidate_list(self) -> None:
        """Invalidate all list-query caches under ``{cache_prefix}:list:*``."""
        await self._cache.delete_pattern(f"{self.cache_prefix}:list:*")


CachedRepositoryMixin = InvalidatingCacheMixin

__all__ = ["CachedRepositoryMixin", "InvalidatingCacheMixin"]
