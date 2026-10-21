"""In-memory cache backend for testing and lightweight scenarios.

Provides an in-process dict-backed :class:`InMemoryCacheBackend` that satisfies
``CacheBackendProtocol`` without external dependencies. TTL is enforced lazily
on read access.

Every operation answers with the protocol's ``Result``. That matters more here
than in a production backend: this is the object packages put behind an
injected ``CacheBackendProtocol`` in their tests, so a fake that returned plain
values would let a caller compile and pass against a shape the real backend
never has.
"""

from __future__ import annotations

import fnmatch
import time
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol
    from quadkit.contracts.infra.cache.exceptions import CacheError


class InMemoryCacheBackend:
    """In-memory implementation of :class:`CacheBackendProtocol`.

    Stores all entries in a plain dict with optional per-entry expiry.
    Suitable for unit tests, local development, and single-process
    deployments that do not require persistence or distributed access.

    Example::

        cache = InMemoryCacheBackend()
        await cache.set("key", "value", ttl=60)
        result = await cache.get("key")
        value = result.unwrap()
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float | None]] = {}

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.monotonic() >= expires_at

    def _live(self, key: str) -> tuple[Any, float | None] | None:
        """Return the live entry for *key*, dropping it when it has expired."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if self._is_expired(entry[1]):
            del self._store[key]
            return None
        return entry

    def _keyspace(self) -> list[str]:
        """Every key, with expired entries discarded on the way through."""
        return [key for key in list(self._store) if self._live(key) is not None]

    async def get(self, key: str) -> Result[Any | None, CacheError]:
        """Get a value from the cache.

        Args:
            key: The cache key to retrieve.

        Returns:
            Ok(value) when the key is live, Ok(None) when it is missing or
            expired. The in-memory backend has no failure mode to report.
        """
        entry = self._live(key)
        return Ok(entry[0] if entry is not None else None)

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> Result[None, CacheError]:
        """Set a value in the cache with optional TTL in seconds."""
        self._store[key] = (value, time.monotonic() + ttl if ttl is not None else None)
        return Ok(None)

    async def delete(self, key: str) -> Result[bool, CacheError]:
        """Delete a key. Returns Ok(True) if it existed, Ok(False) otherwise."""
        if self._live(key) is None:
            self._store.pop(key, None)
            return Ok(False)
        del self._store[key]
        return Ok(True)

    async def delete_many(self, keys: list[str]) -> Result[int, CacheError]:
        """Delete multiple keys, returning how many were present."""
        removed = 0
        for key in keys:
            if (await self.delete(key)).unwrap() is True:
                removed += 1
        return Ok(removed)

    async def delete_pattern(self, pattern: str) -> Result[int, CacheError]:
        """Delete every key matching a glob-style *pattern*."""
        matching = [key for key in self._keyspace() if fnmatch.fnmatch(key, pattern)]
        return await self.delete_many(matching)

    async def exists(self, key: str) -> Result[bool, CacheError]:
        """Return Ok(True) while the key is present and unexpired."""
        return Ok(self._live(key) is not None)

    async def clear(self) -> Result[None, CacheError]:
        """Remove all entries from the cache."""
        self._store.clear()
        return Ok(None)

    async def get_many(self, keys: list[str]) -> Result[dict[str, Any], CacheError]:
        """Get multiple values, omitting missing or expired keys."""
        found: dict[str, Any] = {}
        for key in keys:
            entry = self._live(key)
            if entry is not None:
                found[key] = entry[0]
        return Ok(found)

    async def set_many(
        self, items: dict[str, Any], ttl: int | None = None
    ) -> Result[None, CacheError]:
        """Set multiple key-value pairs with the same optional TTL."""
        for key, value in items.items():
            await self.set(key, value, ttl)
        return Ok(None)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return a healthy status — an in-memory cache is always available."""
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            component="in_memory_cache",
            details={"entries": len(self._keyspace())},
        )


#: Protocol conformance is checked by the type checker, not silenced: the fake
#: is only useful while it has the same shape as the real backend.
_: CacheBackendProtocol = InMemoryCacheBackend()

__all__ = ["InMemoryCacheBackend"]
