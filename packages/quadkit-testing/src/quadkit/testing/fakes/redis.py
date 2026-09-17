"""In-process fake Redis client for docker-free tests."""

from __future__ import annotations

import time
from typing import Any

__all__ = ["FakeRedisClient"]


class FakeRedisClient:
    """In-memory async client compatible with the ``redis.asyncio`` surface used by tests.

    Supports the subset of Redis commands exercised by the optional provider tests:
    ``ping``, ``set`` (with ``ex``/``px``/``nx``/``xx``), ``get``, ``delete``,
    ``exists``, ``expire``, ``ttl``, ``flushdb``, and ``close``.  All data is
    kept in process, so tests never touch the network or a pre-started
    Docker Compose stack.

    Example::

        client = FakeRedisClient()
        assert await client.ping() is True
        assert await client.set("key", "value", ex=60) is True
        assert await client.get("key") == "value"
    """

    def __init__(self) -> None:
        # Maps key → (value, expires_at or None) using time.monotonic().
        self._store: dict[str, tuple[Any, float | None]] = {}

    @staticmethod
    def _is_expired(expires_at: float | None) -> bool:
        """Return ``True`` when *expires_at* is in the past."""
        return expires_at is not None and time.monotonic() > expires_at

    def _get_entry(self, key: str) -> tuple[Any, float | None] | None:
        """Return the live entry for *key*, dropping expired ones."""
        entry = self._store.get(key)
        if entry is None:
            return None
        _value, expires_at = entry
        if self._is_expired(expires_at):
            del self._store[key]
            return None
        return entry

    async def ping(self) -> bool:
        """Return ``True`` — the in-process client is always reachable."""
        return True

    async def set(
        self,
        key: str,
        value: Any,
        ex: float | None = None,
        px: float | None = None,
        nx: bool = False,
        xx: bool = False,
        keepttl: bool = False,
    ) -> bool | None:
        """Store *value* under *key*, honouring expiry and set conditions.

        Mirrors ``redis.asyncio.Redis.set``: returns ``True`` when a value was
        written, ``None`` when ``nx``/``xx`` prevented the write.
        """
        existing = self._get_entry(key)
        if nx and existing is not None:
            return None
        if xx and existing is None:
            return None

        now = time.monotonic()
        if keepttl and existing is not None:
            expires_at = existing[1]
        elif ex is not None:
            expires_at = now + ex
        elif px is not None:
            expires_at = now + (px / 1000.0)
        else:
            expires_at = None

        self._store[key] = (value, expires_at)
        return True

    async def get(self, key: str) -> Any | None:
        """Return the stored value for *key*, or ``None`` when absent/expired."""
        entry = self._get_entry(key)
        if entry is None:
            return None
        return entry[0]

    async def delete(self, *keys: str) -> int:
        """Delete *keys*; return the number of keys actually removed."""
        removed = 0
        for key in keys:
            if self._store.pop(key, None) is not None:
                removed += 1
        return removed

    async def exists(self, *keys: str) -> int:
        """Return how many of *keys* currently hold live values."""
        return sum(1 for key in keys if self._get_entry(key) is not None)

    async def expire(self, key: str, seconds: float) -> bool:
        """Set a TTL of *seconds* on *key*; return ``True`` if the key exists."""
        entry = self._get_entry(key)
        if entry is None:
            return False
        value, _ = entry
        self._store[key] = (value, time.monotonic() + seconds)
        return True

    async def ttl(self, key: str) -> int:
        """Return seconds until *key* expires; ``-2`` when absent, ``-1`` when it never expires."""
        entry = self._get_entry(key)
        if entry is None:
            return -2
        expires_at = entry[1]
        if expires_at is None:
            return -1
        return max(0, int(expires_at - time.monotonic()))

    async def flushdb(self) -> bool:
        """Remove all entries from the fake store."""
        self._store.clear()
        return True

    async def close(self) -> None:
        """No-op — the in-process client holds no connections."""
        return
