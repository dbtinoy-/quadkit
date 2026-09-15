"""In-memory cache backend for testing and lightweight scenarios.

Provides an in-process dict-backed :class:`InMemoryCacheBackend` that
satisfies the ``CacheBackendProtocol`` protocol without any external dependencies.
TTL is enforced lazily on read access.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol


class InMemoryCacheBackend:
    """In-memory implementation of :class:`CacheBackendProtocol`.

    Stores all entries in a plain dict with optional per-entry expiry.
    Suitable for unit tests, local development, and single-process
    deployments that do not require persistence or distributed access.

    Example::

        cache = InMemoryCacheBackend()
        await cache.set("key", "value", ttl=60)
        value = await cache.get("key")
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.monotonic() >= expires_at

    async def get(self, key: str, default: Any = None) -> Any | None:
        """Get a value from the cache.

        Args:
            key: The cache key to retrieve.
            default: Value returned when the key is missing or expired.

        Returns:
            The stored value, or *default* when the key does not exist
            or has expired.
        """
        entry = self._store.get(key)
        if entry is None:
            return default
        value, expires_at = entry
        if self._is_expired(expires_at):
            del self._store[key]
            return default
        return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value in the cache with optional TTL in seconds."""
        expires_at = time.monotonic() + ttl if ttl is not None else None
        self._store[key] = (value, expires_at)
        return True

    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if the key existed, False otherwise."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def delete_many(self, keys: list[str]) -> bool:
        """Delete multiple keys."""
        for key in keys:
            self._store.pop(key, None)
        return True

    async def exists(self, key: str) -> bool:
        """Return True if the key exists and has not expired."""
        return await self.get(key) is not None

    async def clear(self) -> bool:
        """Remove all entries from the cache."""
        self._store.clear()
        return True

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        """Get multiple values, omitting missing or expired keys."""
        result: dict[str, Any] = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    async def set_many(self, items: dict[str, Any], ttl: int | None = None) -> bool:
        """Set multiple key-value pairs with the same optional TTL."""
        for key, value in items.items():
            await self.set(key, value, ttl)
        return True

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return a healthy status — in-memory cache is always available."""
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            component="in_memory_cache",
            details={"entries": len(self._store)},
        )


# Runtime protocol compliance check (raises at import time if protocol drifts)
_: CacheBackendProtocol = InMemoryCacheBackend()  # type: ignore[assignment]

__all__ = ["InMemoryCacheBackend"]
