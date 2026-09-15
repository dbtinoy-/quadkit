"""Fake cache and state store for in-memory test doubles."""

from __future__ import annotations

import time
from typing import Any

__all__ = ["FakeCache", "FakeStateStore"]


class FakeCache:
    """In-memory fake satisfying ``CacheBackendProtocol`` / ``CacheProtocol``.

    Supports TTL expiry using :func:`time.monotonic`.

    Example::

        cache = FakeCache()
        await cache.set("key", "value", ttl=60)
        cache.assert_has_key("key")
    """

    def __init__(self) -> None:
        # Maps key → (value, expires_at or None)
        self._store: dict[str, tuple[Any, float | None]] = {}

    async def get(self, key: str, default: Any = None) -> Any:
        """Return the stored value for *key*, or *default* if absent/expired."""
        entry = self._store.get(key)
        if entry is None:
            return default
        value, expires_at = entry
        if expires_at is not None and time.monotonic() > expires_at:
            del self._store[key]
            return default
        return value

    async def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Store *value* under *key*, optionally expiring after *ttl* seconds."""
        expires_at = time.monotonic() + ttl if ttl is not None else None
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> bool:
        """Delete *key*; return ``True`` if it existed."""
        return self._store.pop(key, None) is not None

    async def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()

    @property
    def stored_keys(self) -> list[str]:
        """Return a snapshot of currently stored keys."""
        return list(self._store.keys())

    def assert_has_key(self, key: str) -> None:
        """Assert *key* is present in the cache."""
        if key not in self._store:
            msg = f"Key {key!r} not in cache. Keys: {list(self._store)}"
            raise AssertionError(msg)

    def assert_value(self, key: str, expected: Any) -> None:
        """Assert *key* maps to *expected*."""
        self.assert_has_key(key)
        actual = self._store[key][0]
        if actual != expected:
            msg = f"Cache[{key!r}]: expected {expected!r}, got {actual!r}"
            raise AssertionError(msg)


class FakeStateStore:
    """In-memory fake satisfying ``StateStoreProtocol`` protocol.

    Example::

        store = FakeStateStore()
        await store.set("session:abc", {"user_id": "u1"})
        value = await store.get("session:abc")
    """

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}

    async def get(self, key: str) -> Any | None:
        """Return the value for *key*, or ``None`` if absent."""
        return self._state.get(key)

    async def set(self, key: str, value: Any) -> None:
        """Store *value* under *key*."""
        self._state[key] = value

    async def delete(self, key: str) -> bool:
        """Delete *key*; return ``True`` if it existed."""
        return self._state.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        """Return ``True`` if *key* has a stored value."""
        return key in self._state

    def clear(self) -> None:
        """Remove all stored entries."""
        self._state.clear()
