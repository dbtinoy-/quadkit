"""RepositoryProtocol method decorators.

Utility decorators for instrumenting repository methods with caching and
timing.  Apply them to concrete repository methods to add cross-cutting
concerns without polluting the core logic.

Example::

    class UserRepository(AbstractRepository[User, str]):
        @cacheable(ttl=300)
        async def get(self, item_id: str) -> User | None:
            return await self._fetch_by_id(item_id)

        @timed(operation="find_active_users")
        async def find_active(self) -> list[User]:
            return await self._fetch_many(skip=0, limit=1000, filters={"active": True})
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import functools
import time
from typing import Any, TypeVar

from quadkit.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def timed(operation: str | None = None) -> Callable[[F], F]:
    """Decorator that logs the wall-clock duration of an async repository method.

    Args:
        operation: Human-readable operation name for the log entry.  Defaults
            to ``<class>.<method>``.

    Returns:
        Decorator that wraps the target coroutine function.

    Example::

        @timed(operation="user.find_active")
        async def find_active(self) -> list[User]: ...
    """

    def decorator(fn: F) -> F:
        op_name = operation or fn.__qualname__

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug(
                    "repository_operation_completed",
                    operation=op_name,
                    elapsed_ms=round(elapsed_ms, 3),
                )
                return result
            except Exception as e:  # noqa: BLE001 — timing decorator must capture any failure type
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.warning(
                    "repository_operation_failed",
                    operation=op_name,
                    elapsed_ms=round(elapsed_ms, 3),
                    error=str(e),
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def cacheable(
    *,
    ttl: int = 300,
    key_prefix: str | None = None,
) -> Callable[[F], F]:
    """Decorator that caches the result of an async repository ``get`` method.

    The cache key is built from *key_prefix* (or the method's qualified name)
    and the positional arguments joined by ``:``.

    The decorated method must accept a ``cache`` keyword argument of type
    ``CacheBackendProtocol | None``; when ``cache`` is ``None`` the decorator is a
    transparent pass-through.

    Args:
        ttl: Cache time-to-live in seconds.
        key_prefix: Prefix for the cache key.  Defaults to the method's fully
            qualified name.

    Returns:
        Decorator that wraps the target coroutine function.

    Example::

        @cacheable(ttl=60, key_prefix="user")
        async def get(self, item_id: str) -> User | None: ...
    """

    def decorator(fn: F) -> F:
        prefix = key_prefix or fn.__qualname__

        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # The first argument after self is typically the entity id.
            cache = kwargs.get("cache") or (
                getattr(args[0], "cache", None) if args else None
            )
            if cache is None:
                return await fn(*args, **kwargs)

            # Build cache key from positional args (excluding self).
            key_parts = [prefix] + [str(a) for a in args[1:]]
            cache_key = ":".join(key_parts)

            cached = await cache.get(cache_key)
            if cached is not None:
                logger.debug("repository_cache_hit", key=cache_key)
                return cached

            result = await fn(*args, **kwargs)
            if result is not None:
                await cache.set(cache_key, result, ttl=ttl)
                logger.debug("repository_cache_set", key=cache_key, ttl=ttl)
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["cacheable", "timed"]
