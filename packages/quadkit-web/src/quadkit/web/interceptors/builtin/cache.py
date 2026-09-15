"""Cache interceptor for HTTP response caching.

Provides HTTP response caching based on cache headers.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from quadkit.primitives import clock as ambient_clock
from quadkit.web.protocols import (
    CallHandlerProtocol,
    ExecutionContextProtocol,
    WebInterceptorProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class CacheInterceptor(WebInterceptorProtocol):
    """Interceptor that handles HTTP response caching.

    Respects Cache-Control headers and can cache responses based on
    request path and other parameters.

    Example:
        ```python
        # Global cache with 60 second TTL
        router.add_interceptor(CacheInterceptor(ttl=60))
        ```
    """

    def __init__(
        self,
        ttl: int = 300,
        cache_key_builder: Callable[[Any], str] | None = None,
    ):
        """Initialize the cache interceptor.

        Args:
            ttl: Default time-to-live in seconds for cached responses.
            cache_key_builder: Optional custom function to build cache keys.
        """
        self._ttl = ttl
        self._cache_key_builder = cache_key_builder or self._default_cache_key
        self._cache: dict[str, tuple[Any, float]] = {}

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        """Intercept and handle caching.

        Args:
            context: The execution context.
            next_handler: The next handler in the chain.

        Returns:
            Cached response or fresh response from handler.
        """
        request = context.request

        # Check if this is a cacheable method
        method = getattr(request, "method", "GET")
        if method != "GET":
            return await next_handler.handle()

        # Build cache key
        cache_key = self._cache_key_builder(request)

        # Check cache
        if cache_key in self._cache:
            result, expiry = self._cache[cache_key]
            timestamp = ambient_clock.timestamp()
            if timestamp < expiry:
                # Add cache hit header
                if hasattr(result, "headers"):
                    result.headers["X-Cache"] = "HIT"
                return result
            # Expired - remove from cache
            del self._cache[cache_key]

        # Execute handler
        result = await next_handler.handle()

        # Check if response is cacheable
        if result is not None and self._is_cacheable(result):
            timestamp = ambient_clock.timestamp()
            # Store in cache
            self._cache[cache_key] = (result, timestamp + self._ttl)

            # Add cache miss header
            if hasattr(result, "headers"):
                result.headers["X-Cache"] = "MISS"

        return result

    def _default_cache_key(self, request: Any) -> str:
        """Build default cache key from request.

        Args:
            request: The HTTP request.

        Returns:
            Cache key string.
        """
        url = getattr(request, "url", None)
        path = url.path if url is not None else "/"

        # Include query params in cache key
        query_params = str(getattr(request, "query_params", ""))

        key_data = f"{path}:{query_params}"
        return hashlib.md5(key_data.encode(), usedforsecurity=False).hexdigest()

    def _is_cacheable(self, result: Any) -> bool:
        """Check if a response is cacheable.

        Args:
            result: The response to check.

        Returns:
            True if the response is cacheable.
        """
        # Check status code
        status_code = getattr(result, "status_code", 200)
        if status_code != 200:
            return False

        # Check Cache-Control header
        if hasattr(result, "headers"):
            cache_control = result.headers.get("cache-control", "")
            if "no-store" in cache_control.lower():
                return False
            if "private" in cache_control.lower():
                return False

        return True

    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()


__all__ = ["CacheInterceptor"]
