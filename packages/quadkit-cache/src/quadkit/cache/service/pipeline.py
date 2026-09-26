"""Batch/pipeline cache operations mixin.

This module provides the :class:`PipelineMixin` which adds bulk ``get_many``,
``set_many``, and ``delete_many`` operations to :class:`CacheService`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    import asyncio

logger = get_logger(__name__)

_BACKEND_ERRORS = (
    RuntimeError,
    OSError,
    ConnectionError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
)


class PipelineMixin:
    """Mixin providing batch/pipeline cache operations for CacheService.

    Requires the host class to provide ``_get_namespaced_key``,
    ``_get_backend``, ``_metrics_lock``, and ``_metrics``.
    """

    # Declared here so type checkers understand the required host attributes;
    # the actual values are set by CacheService.__init__.
    _metrics_lock: asyncio.Lock
    _metrics: dict[str, int]

    async def get_many(
        self,
        keys: list[str],
        backend: str | None = None,
    ) -> dict[str, Any]:
        """Get multiple values from cache.

        Args:
            keys: List of cache keys.
            backend: Backend name (uses default if ``None``).

        Returns:
            Dictionary of key-value pairs found in cache.
        """
        try:
            namespaced_keys = [self._get_namespaced_key(k) for k in keys]  # type: ignore[attr-defined]
            backend_instance = self._get_backend(backend)  # type: ignore[attr-defined]
            namespaced_result = await backend_instance.get_many(namespaced_keys)
            # Backends report batch results via Result — unwrap the Ok payload
            # (a Result object is not iterable / indexable).
            if hasattr(namespaced_result, "is_ok"):
                if not namespaced_result.is_ok():
                    logger.warning(
                        "Cache get_many failed: %s", namespaced_result.unwrap_err()
                    )
                    return {}
                namespaced_result = namespaced_result.unwrap()
            result: dict[str, Any] = {}
            for original_key, namespaced_key in zip(keys, namespaced_keys, strict=True):
                if namespaced_key in namespaced_result:
                    result[original_key] = namespaced_result[namespaced_key]
            return result

        except _BACKEND_ERRORS as e:
            logger.warning("Cache get_many failed: %s", e)
            async with self._metrics_lock:
                self._metrics["errors"] += 1
            return {}

        finally:
            async with self._metrics_lock:
                self._metrics["operations"] += 1

    async def set_many(
        self,
        items: dict[str, Any],
        ttl: int | None = None,
        backend: str | None = None,
    ) -> bool:
        """Set multiple values in cache.

        Args:
            items: Dictionary of key-value pairs.
            ttl: Time-to-live in seconds.
            backend: Backend name (uses default if ``None``).

        Returns:
            ``True`` if successful, ``False`` otherwise.
        """
        try:
            namespaced_items = {
                self._get_namespaced_key(k): v  # type: ignore[attr-defined]
                for k, v in items.items()
            }
            backend_instance = self._get_backend(backend)  # type: ignore[attr-defined]
            actual_ttl = self._add_ttl_jitter(ttl)  # type: ignore[attr-defined]
            success = await backend_instance.set_many(namespaced_items, actual_ttl)
            if hasattr(success, "is_ok"):
                return bool(success.is_ok())
            return bool(success)

        except _BACKEND_ERRORS as e:
            logger.warning("Cache set_many failed: %s", e)
            async with self._metrics_lock:
                self._metrics["errors"] += 1
            return False

        finally:
            async with self._metrics_lock:
                self._metrics["operations"] += 1

    async def delete_many(
        self,
        keys: list[str],
        backend: str | None = None,
    ) -> bool:
        """Delete multiple values from cache.

        Args:
            keys: List of cache keys.
            backend: Backend name (uses default if ``None``).

        Returns:
            ``True`` if successful, ``False`` otherwise.
        """
        try:
            namespaced_keys = [self._get_namespaced_key(k) for k in keys]  # type: ignore[attr-defined]
            backend_instance = self._get_backend(backend)  # type: ignore[attr-defined]
            result = await backend_instance.delete_many(namespaced_keys)
            if hasattr(result, "is_ok"):
                return bool(result.is_ok())
            return bool(result)

        except _BACKEND_ERRORS as e:
            logger.warning("Cache delete_many failed: %s", e)
            async with self._metrics_lock:
                self._metrics["errors"] += 1
            return False

        finally:
            async with self._metrics_lock:
                self._metrics["operations"] += 1
