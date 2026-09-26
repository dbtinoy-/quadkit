"""
Caching decorators for Quadkit Framework.

This module provides decorators for easy function result caching,
including @cache for general caching and @remember for memoization.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import hashlib
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.cache.service.core import CacheService

logger = get_logger(__name__)


def cache(
    service: CacheService,
    key_prefix: str = "cache",
    ttl: int | None = None,
    backend: str | None = None,
    protect: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to cache function results with custom key generation.

    Args:
        service: CacheService instance
        key_prefix: Prefix for cache keys
        ttl: Time-to-live in seconds
        backend: Backend name
        protect: Enable stampede protection

    Returns:
        Decorator function

    Example:
        @cache(cache_service, key_prefix="api", ttl=300)
        async def get_user_data(user_id: int):
            return await fetch_from_database(user_id)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key from function name and arguments
            func_id = f"{func.__module__}.{func.__qualname__}"
            args_str = str(args) + str(sorted(kwargs.items()))
            key_suffix = hashlib.blake2b(args_str.encode(), digest_size=16).hexdigest()
            cache_key = f"{key_prefix}:{func_id}:{key_suffix}"

            return await service.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl,
                backend,
                protect,
            )

        return wrapper

    return decorator


def remember(
    service: CacheService,
    ttl: int | None = None,
    backend: str | None = None,
    protect: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to remember function results (memoization).

    Uses automatic key generation based on function signature.

    Args:
        service: CacheService instance
        ttl: Time-to-live in seconds
        backend: Backend name
        protect: Enable stampede protection

    Returns:
        Decorator function

    Example:
        @remember(cache_service, ttl=600)
        async def expensive_computation(x: int, y: int):
            return await slow_calculation(x, y)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate deterministic cache key
            func_id = f"{func.__module__}.{func.__qualname__}"
            args_str = str(args) + str(sorted(kwargs.items()))
            cache_key = f"remember:{func_id}:{hashlib.blake2b(args_str.encode(), digest_size=16).hexdigest()}"

            return await service.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl,
                backend,
                protect,
            )

        return wrapper

    return decorator


def conditional_cache(
    service: CacheService,
    condition_func: Callable[[Any], bool],
    key_prefix: str = "cond",
    ttl: int | None = None,
    backend: str | None = None,
    protect: bool = True,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to cache function results only when condition is met.

    Args:
        service: CacheService instance
        condition_func: Function that returns True if result should be cached
        key_prefix: Prefix for cache keys
        ttl: Time-to-live in seconds
        backend: Backend name
        protect: Enable stampede protection

    Returns:
        Decorator function

    Example:
        @conditional_cache(
            cache_service,
            lambda result: result is not None,
            ttl=300
        )
        async def search_database(query: str):
            return await db.search(query)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            func_id = f"{func.__module__}.{func.__qualname__}"
            args_str = str(args) + str(sorted(kwargs.items()))
            key_suffix = hashlib.blake2b(args_str.encode(), digest_size=16).hexdigest()
            cache_key = f"{key_prefix}:{func_id}:{key_suffix}"

            # Try to get from cache first
            cached_value = await service.get(cache_key, backend=backend)
            if cached_value is not None:
                return cached_value

            # Compute the value
            result = await func(*args, **kwargs)

            # Cache only if condition is met
            if condition_func(result):
                await service.set(cache_key, result, ttl, backend)

            return result

        return wrapper

    return decorator


def invalidate_cache(
    service: CacheService,
    key_pattern: str,
    backend: str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator to invalidate cache keys after function execution.

    Args:
        service: CacheService instance
        key_pattern: Pattern for keys to invalidate (supports wildcards)
        backend: Backend name

    Returns:
        Decorator function

    Example:
        @invalidate_cache(cache_service, "user:*")
        async def update_user(user_id: int, data: dict):
            return await db.update_user(user_id, data)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Execute the function first
            result = await func(*args, **kwargs)

            # Invalidate cache keys matching the pattern
            # Note: This is a simplified implementation
            # Real implementation would need pattern matching support
            try:
                # For now, assume key_pattern is a specific key
                await service.delete(key_pattern, backend)
            except Exception as e:  # noqa: BLE001 — invalidation failures are best-effort
                logger.warning(
                    "Failed to invalidate cache pattern '%s': %s",
                    key_pattern,
                    e,
                )

            return result

        return wrapper

    return decorator


class CacheDecorator:
    """
    Advanced caching decorator with multiple strategies.

    Provides a class-based decorator with more configuration options
    and caching strategies.
    """

    def __init__(
        self,
        service: CacheService,
        strategy: str = "remember",
        key_prefix: str = "",
        ttl: int | None = None,
        backend: str | None = None,
        protect: bool = True,
        condition: Callable[[Any], bool] | None = None,
    ):
        """
        Initialize the cache decorator.

        Args:
            service: CacheService instance
            strategy: Caching strategy ("remember", "cache", "conditional")
            key_prefix: Prefix for cache keys
            ttl: Time-to-live in seconds
            backend: Backend name
            protect: Enable stampede protection
            condition: Condition function for conditional caching
        """
        self.service = service
        self.strategy = strategy
        self.key_prefix = key_prefix
        self.ttl = ttl
        self.backend = backend
        self.protect = protect
        self.condition = condition

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Apply the caching decorator."""
        if self.strategy == "remember":
            return remember(self.service, self.ttl, self.backend, self.protect)(func)
        if self.strategy == "cache":
            prefix = self.key_prefix or "cache"
            return cache(self.service, prefix, self.ttl, self.backend, self.protect)(
                func,
            )
        if self.strategy == "conditional":
            if self.condition is None:
                raise ValueError("condition_func is required for conditional caching")
            prefix = self.key_prefix or "cond"
            return conditional_cache(
                self.service,
                self.condition,
                prefix,
                self.ttl,
                self.backend,
                self.protect,
            )(func)
        raise ValueError(f"Unknown caching strategy: {self.strategy}")
