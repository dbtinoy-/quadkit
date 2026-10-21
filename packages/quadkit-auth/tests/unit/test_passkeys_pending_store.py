from __future__ import annotations

from typing import Any

import pytest

from quadkit.auth.authn.passkeys import _PendingStore
from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.config.operation import CacheOperationConfig
from quadkit.contracts.infra.cache.exceptions import CacheError, CacheWriteError
from quadkit.primitives import clock as ambient_clock
from quadkit.result import Err, Ok, Result


class DummyCache:
    """Small cache double that follows CacheBackendProtocol's Result contract."""

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> Result[None, CacheError]:
        self._store[key] = value
        return Ok(None)

    async def get(self, key: str) -> Result[Any | None, CacheError]:
        return Ok(self._store.get(key))

    async def delete(self, key: str) -> Result[bool, CacheError]:
        return Ok(self._store.pop(key, None) is not None)


class FailingCache:
    """Cache double returning a typed error for each data-plane operation."""

    def __init__(self, error: CacheError) -> None:
        self.error = error

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> Result[None, CacheError]:
        return Err(self.error)

    async def get(self, key: str) -> Result[Any | None, CacheError]:
        return Err(self.error)

    async def delete(self, key: str) -> Result[bool, CacheError]:
        return Err(self.error)


@pytest.mark.asyncio
async def test_pending_store_inmemory():
    store = _PendingStore()
    value = {"x": 1, "metadata": {"attempts": [1]}}
    await store.set("k1", value, ttl=1)

    # Local fallback should have the same value semantics as the JSON-backed
    # cache path: callers cannot mutate a stored ceremony through an alias.
    value["metadata"]["attempts"].append(2)
    stored = await store.get("k1")
    assert stored == {"x": 1, "metadata": {"attempts": [1]}}
    assert stored is not None
    stored["metadata"]["attempts"].append(3)
    assert await store.get("k1") == {"x": 1, "metadata": {"attempts": [1]}}
    await store.delete("k1")
    assert await store.get("k1") is None


@pytest.mark.asyncio
async def test_pending_store_inmemory_expires_at_ttl_boundary(monkeypatch):
    now = 100.0
    monkeypatch.setattr(ambient_clock, "monotonic", lambda: now)
    store = _PendingStore()

    await store.set("expires", {"challenge": "abc"}, ttl=5)
    assert await store.get("expires") == {"challenge": "abc"}

    now = 105.0
    assert await store.get("expires") is None
    assert "expires" not in store._store


@pytest.mark.asyncio
async def test_pending_store_cache_backend():
    cache = DummyCache()
    store = _PendingStore(cache)

    await store.set("k2", {"y": 2}, ttl=10)
    assert isinstance(cache._store["k2"], str)
    assert await store.get("k2") == {"y": 2}
    await store.delete("k2")
    assert await store.get("k2") is None


@pytest.mark.asyncio
async def test_pending_store_decodes_byte_payload_and_rejects_non_objects():
    cache = DummyCache()
    store = _PendingStore(cache)
    cache._store["bytes"] = b'{"challenge":"abc"}'
    cache._store["not-an-object"] = "[]"

    assert await store.get("bytes") == {"challenge": "abc"}
    with pytest.raises(TypeError, match="JSON object"):
        await store.get("not-an-object")


@pytest.mark.asyncio
async def test_pending_store_quadkit_memory_backend_round_trips_json_text():
    """Structured cache backends must not turn serialized bytes into ``b'...'``."""
    cache = MemoryCacheBackend(config=CacheOperationConfig(default_ttl=300))
    store = _PendingStore(cache)

    await store.set("k3", {"challenge": "abc", "user_id": "u1"}, ttl=10)
    assert await store.get("k3") == {"challenge": "abc", "user_id": "u1"}


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
@pytest.mark.asyncio
async def test_pending_store_propagates_cache_result_errors(operation: str) -> None:
    error = (
        CacheWriteError("ceremony", "backend unavailable")
        if operation == "set"
        else CacheError("cache backend unavailable")
    )
    store = _PendingStore(FailingCache(error))

    async def exercise_operation() -> None:
        if operation == "get":
            await store.get("ceremony")
        elif operation == "set":
            await store.set("ceremony", {"challenge": "abc"})
        else:
            await store.delete("ceremony")

    with pytest.raises(type(error)) as exc_info:
        await exercise_operation()
    assert exc_info.value is error
