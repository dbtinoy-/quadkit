"""Contract compliance suite for ``CacheBackendProtocol`` implementations.

Subclass :class:`CacheBackendCompliance` and implement
:meth:`create_backend` to verify any cache backend satisfies the
``CacheBackendProtocol`` contract::

    from quadkit.testing.compliance import CacheBackendCompliance

    class TestMyCache(CacheBackendCompliance):
        async def create_backend(self):
            return MyInMemoryCache()
"""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from typing import Any

import pytest

__all__ = ["CacheBackendCompliance"]


class CacheBackendCompliance:
    """Reusable test suite for any ``CacheBackendProtocol`` implementation.

    Subclass and implement :meth:`create_backend`:

    .. code-block:: python

        class TestRedisCache(CacheBackendCompliance):
            async def create_backend(self):
                return RedisCacheBackend("redis://localhost")
    """

    @abstractmethod
    async def create_backend(self) -> Any:
        """Return a fresh, empty instance of the backend under test."""
        ...

    # ------------------------------------------------------------------
    # Core contract tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_set_and_get(self) -> None:
        """set then get returns the stored value."""
        backend = await self.create_backend()
        await backend.set("key", "value")
        result = await backend.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_get_missing_returns_default(self) -> None:
        """get on a missing key returns the default."""
        backend = await self.create_backend()
        result = await backend.get("nonexistent", "fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none_without_default(self) -> None:
        """get on a missing key returns None when no default is given."""
        backend = await self.create_backend()
        result = await backend.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_key(self) -> None:
        """delete returns True and removes the key."""
        backend = await self.create_backend()
        await backend.set("key", "value")
        deleted = await backend.delete("key")
        assert deleted is True
        assert await backend.get("key") is None

    @pytest.mark.asyncio
    async def test_delete_missing_key(self) -> None:
        """delete on a missing key returns False."""
        backend = await self.create_backend()
        deleted = await backend.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """clear removes all stored entries."""
        backend = await self.create_backend()
        await backend.set("a", 1)
        await backend.set("b", 2)
        await backend.clear()
        assert await backend.get("a") is None
        assert await backend.get("b") is None

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self) -> None:
        """set on an existing key overwrites the value."""
        backend = await self.create_backend()
        await backend.set("key", "first")
        await backend.set("key", "second")
        assert await backend.get("key") == "second"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self) -> None:
        """Values with TTL expire and are no longer returned."""
        backend = await self.create_backend()
        await backend.set("key", "value", ttl=0.05)
        await asyncio.sleep(0.1)
        result = await backend.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_ttl_does_not_expire(self) -> None:
        """Values without TTL persist and are accessible."""
        backend = await self.create_backend()
        await backend.set("key", "value")
        await asyncio.sleep(0.1)  # small delay
        result = await backend.get("key")
        assert result == "value"

    @pytest.mark.asyncio
    async def test_stores_various_value_types(self) -> None:
        """The backend accepts strings, ints, dicts, and lists."""
        backend = await self.create_backend()
        for key, value in [
            ("str", "hello"),
            ("int", 42),
            ("dict", {"x": 1}),
            ("list", [1, 2, 3]),
        ]:
            await backend.set(key, value)
            assert await backend.get(key) == value
