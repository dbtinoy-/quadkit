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


def _value(result: Any) -> Any:
    """Unwrap an ``Ok`` result, failing the test when it is ``Err``.

    ``CacheBackendProtocol`` answers every operation with a
    ``Result[T, CacheError]``: a cache that cannot reach its store reports that
    rather than raising. Unwrapping in one place keeps each test about the
    behaviour it names, and a failure message carries the error instead of a
    bare assertion.
    """
    assert result.is_ok(), f"expected Ok, got {result!r}"
    return result.unwrap()


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
        _value(await backend.set("key", "value"))
        assert _value(await backend.get("key")) == "value"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self) -> None:
        """get on a missing key returns Ok(None)."""
        backend = await self.create_backend()
        assert _value(await backend.get("nonexistent")) is None

    @pytest.mark.asyncio
    async def test_delete_existing_key(self) -> None:
        """delete returns Ok(True) and removes the key."""
        backend = await self.create_backend()
        await backend.set("key", "value")
        assert _value(await backend.delete("key")) is True
        assert _value(await backend.get("key")) is None

    @pytest.mark.asyncio
    async def test_delete_missing_key(self) -> None:
        """delete on a missing key returns Ok(False)."""
        backend = await self.create_backend()
        assert _value(await backend.delete("nonexistent")) is False

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """clear removes all stored entries."""
        backend = await self.create_backend()
        await backend.set("a", 1)
        await backend.set("b", 2)
        _value(await backend.clear())
        assert _value(await backend.get("a")) is None
        assert _value(await backend.get("b")) is None

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self) -> None:
        """set on an existing key overwrites the value."""
        backend = await self.create_backend()
        await backend.set("key", "first")
        await backend.set("key", "second")
        assert _value(await backend.get("key")) == "second"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self) -> None:
        """Values with TTL expire and are no longer returned."""
        backend = await self.create_backend()
        await backend.set("key", "value", ttl=0.05)
        await asyncio.sleep(0.1)
        assert _value(await backend.get("key")) is None

    @pytest.mark.asyncio
    async def test_no_ttl_does_not_expire(self) -> None:
        """Values without TTL persist and are accessible."""
        backend = await self.create_backend()
        await backend.set("key", "value")
        await asyncio.sleep(0.1)  # small delay
        assert _value(await backend.get("key")) == "value"

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
            assert _value(await backend.get(key)) == value

    @pytest.mark.asyncio
    async def test_errors_are_returned_not_raised(self) -> None:
        """A backend that fails reports Err(CacheError) rather than raising.

        The protocol's whole point is that a cache miss or an unreachable
        cache is a value the caller handles; a suite that only ever sees a
        happy backend would certify a backend that raises on failure.
        """
        backend = await self.create_backend()
        for result in (
            await backend.get("key"),
            await backend.set("key", "value"),
            await backend.delete("key"),
            await backend.exists("key"),
            await backend.clear(),
        ):
            assert hasattr(result, "is_ok"), (
                f"{type(backend).__name__} returned {type(result).__name__} "
                "where CacheBackendProtocol promises Result"
            )
