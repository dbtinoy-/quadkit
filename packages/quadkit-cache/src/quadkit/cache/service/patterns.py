"""Cache-aside, write-through, and stampede-protected pattern mixin.

This module provides the :class:`PatternsMixin` which adds high-level caching
patterns (``get_or_set``, ``remember``, etc.) to :class:`CacheService`.
"""

from __future__ import annotations

from functools import wraps
import hashlib
import inspect
from typing import TYPE_CHECKING, Any, TypeVar

from quadkit.logging import get_logger
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from collections.abc import Callable

_T = TypeVar("_T")
_E = TypeVar("_E", bound=Exception)

logger = get_logger(__name__)


class PatternsMixin:
    """Mixin providing cache-aside and stampede-protected patterns for CacheService.

    Requires the host class to provide ``get``, ``set``, ``_protection``,
    and ``_metrics``.
    """

    # Declared here so type checkers understand the required host attribute;
    # the actual value is set by CacheService.__init__.
    _metrics: dict[str, int]

    async def get_or_set(
        self,
        key: str,
        default_func: Callable[[], Any],
        ttl: int | None = None,
        backend: str | None = None,
        protect: bool = True,
    ) -> Any:
        """Get a value from cache or compute and set it.

        Implements the cache-aside pattern with optional cache stampede
        protection.

        Args:
            key: Cache key.
            default_func: Function to compute value if not cached.
            ttl: Time-to-live in seconds.
            backend: Backend name (uses default if ``None``).
            protect: Enable stampede protection.

        Returns:
            Cached or computed value.
        """
        value = await self.get(key, backend=backend)  # type: ignore[attr-defined]
        if value is not None:
            return value

        protection = self._protection  # type: ignore[attr-defined]
        if protect and protection:
            value = await protection.get_or_compute(
                key,
                default_func,
                ttl=ttl or 300,
            )
            # Protection caches under its own ``cache:`` namespace with a
            # wrapped entry envelope; mirror the plain value into the
            # service's namespace so get/exists/delete see it too.
            await self.set(key, value, ttl, backend)  # type: ignore[attr-defined]
            return value

        try:
            result = default_func()
            if inspect.isawaitable(result):
                value = await result
            else:
                value = result
            await self.set(key, value, ttl, backend)  # type: ignore[attr-defined]
            return value
        except Exception as e:
            logger.warning("Failed to compute value for key '%s': %s", key, e)
            self._metrics["errors"] += 1
            raise

    async def get_or_set_result(
        self,
        key: str,
        default_func: Callable[[], Result[_T, _E] | Any],
        ttl: int | None = None,
        backend: str | None = None,
        protect: bool = True,
    ) -> Result[_T, _E]:
        """Get a value from cache or compute and set it, returning ``Result[T, E]``.

        Implements the cache-aside pattern with optional cache stampede
        protection. If the cached value exists, it returns ``Ok(value)``. If
        not, calls *default_func* which should return ``Result[T, E]``. On
        success, caches the unwrapped value.

        Args:
            key: Cache key.
            default_func: Function that returns ``Result[T, E]`` or ``T``.
            ttl: Time-to-live in seconds.
            backend: Backend name (uses default if ``None``).
            protect: Enable stampede protection.

        Returns:
            ``Result[T, E]`` wrapping either cached or computed value, or error.
        """
        value = await self.get(key, backend=backend)  # type: ignore[attr-defined]
        if value is not None:
            return Ok(value)

        try:
            result_or_value = default_func()
            if inspect.isawaitable(result_or_value):
                result_or_value = await result_or_value

            if isinstance(result_or_value, Result):
                if result_or_value.is_ok():
                    unwrapped = result_or_value.unwrap()
                    await self.set(key, unwrapped, ttl, backend)  # type: ignore[attr-defined]
                return result_or_value

            await self.set(key, result_or_value, ttl, backend)  # type: ignore[attr-defined]
            return Ok(result_or_value)
        except Exception as e:  # noqa: BLE001 — log any compute failure; the error still re-raises
            logger.warning(
                "Failed to compute result for key '%s': %s", key, type(e).__name__
            )
            self._metrics["errors"] += 1
            raise

    async def get_or_compute(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: int | None = None,
        backend: str | None = None,
    ) -> Any:
        """Get a value from cache or compute it with stampede protection.

        Convenience alias for ``get_or_set(..., protect=True)`` that follows
        the naming convention used in the platform contracts.

        Args:
            key: Cache key.
            factory: Zero-argument callable (sync or async) that produces the
                value when a cache miss occurs.
            ttl: Time-to-live in seconds.  ``None`` uses backend default.
            backend: Named backend to use.  ``None`` uses the default backend.

        Returns:
            Cached value or freshly computed value.
        """
        return await self.get_or_set(
            key, factory, ttl=ttl, backend=backend, protect=True
        )

    async def remember(
        self,
        key: str | None = None,
        ttl: int | None = None,
        backend: str | None = None,
        protect: bool = True,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to cache function results.

        Args:
            key: Custom cache key (auto-generated if ``None``).
            ttl: Time-to-live in seconds.
            backend: Backend name.
            protect: Enable stampede protection.

        Returns:
            Decorator function.
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_key = key
                if cache_key is None:
                    func_id = f"{func.__module__}.{func.__qualname__}"
                    args_str = str(args) + str(sorted(kwargs.items()))
                    cache_key = (
                        f"func:{func_id}:"
                        f"{hashlib.blake2b(args_str.encode(), digest_size=16).hexdigest()}"
                    )

                return await self.get_or_set(
                    cache_key,
                    lambda: func(*args, **kwargs),
                    ttl,
                    backend,
                    protect,
                )

            return wrapper

        return decorator
