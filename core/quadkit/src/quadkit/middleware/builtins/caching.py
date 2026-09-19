"""Caching middleware — result caching via CacheBackendProtocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
    from quadkit.middleware.types import NextHandler

logger = get_logger(__name__)


class CachingMiddleware:
    """Middleware that caches handler results using a key function.

    When the same cache key is seen again within the TTL window, the
    cached result is returned without invoking the downstream handler.

    Args:
        key_func: A callable ``(context) -> str`` producing the cache key.
        cache: A :class:`~quadkit.contracts.cache.protocols.CacheBackendProtocol`
            instance used for result storage.
        ttl: Time-to-live for cached entries in seconds.
    """

    __slots__ = ("_cache", "_key_func", "_ttl")

    def __init__(
        self,
        key_func: Callable[[Any], str],
        cache: CacheBackendProtocol,
        ttl: float = 60.0,
    ) -> None:
        self._key_func = key_func
        self._cache = cache
        self._ttl = ttl

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Return cached result if available, otherwise compute and cache."""
        cache_key = self._key_func(context)
        stored = await self._cache.get(cache_key)
        cached = stored.unwrap() if stored.is_ok() else None
        if cached is not None:
            logger.debug("middleware_cache_hit", key=cache_key)
            return cached

        result = await next_handler(context)
        await self._cache.set(cache_key, result, ttl=int(self._ttl))
        logger.debug("middleware_cache_miss", key=cache_key)
        return result


__all__ = ["CachingMiddleware"]
