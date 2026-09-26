"""Unit tests for the CachedRepository read-through wrapper."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core.result import Err, Ok
from quadkit.sql.repositories.cached import CachedRepository


class _FakeCache:
    """In-memory CacheBackendProtocol double (Result-based API)."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}
        self.deleted: list[str] = []

    async def get(self, key: str) -> Any:
        if key in self.store:
            return Ok(self.store[key])
        return Err("miss")

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self.store[key] = value

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.store.pop(key, None)


class _InnerRepo:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.data = {"1": {"id": "1", "name": "Alice"}}

    async def find_by_id(self, key: Any) -> Any:
        self.calls.append(("find_by_id", key))
        return self.data.get(key)

    async def find_many(self, **kwargs: Any) -> list[Any]:
        self.calls.append(("find_many", kwargs))
        return list(self.data.values())

    async def count(self, **kwargs: Any) -> int:
        self.calls.append(("count", kwargs))
        return len(self.data)

    async def create(self, entity: Any) -> Any:
        self.calls.append(("create", entity))
        return entity

    async def update(self, entity: Any) -> Any:
        self.calls.append(("update", entity))
        return entity

    async def delete_by_id(self, key: Any) -> bool:
        self.calls.append(("delete_by_id", key))
        return True

    def custom_thing(self) -> str:
        return "proxied"


@pytest.fixture
def parts() -> tuple[_InnerRepo, _FakeCache, CachedRepository]:
    inner, cache = _InnerRepo(), _FakeCache()
    return inner, cache, CachedRepository(inner, cache, prefix="users")


class TestReadThrough:
    @pytest.mark.asyncio
    async def test_find_by_id_miss_then_hit(self, parts: Any) -> None:
        inner, cache, repo = parts
        assert await repo.find_by_id("1") == {"id": "1", "name": "Alice"}
        assert inner.calls.count(("find_by_id", "1")) == 1
        # Second call is served from the cache.
        assert await repo.find_by_id("1") == {"id": "1", "name": "Alice"}
        assert inner.calls.count(("find_by_id", "1")) == 1
        # The version key and an id key are in the cache.
        assert any(k.endswith(":__version__") for k in cache.store)
        assert any(k.endswith(":id:1") for k in cache.store)

    @pytest.mark.asyncio
    async def test_find_by_id_none_result_not_cached(self, parts: Any) -> None:
        inner, cache, repo = parts
        assert await repo.find_by_id("missing") is None
        assert await repo.find_by_id("missing") is None
        assert inner.calls.count(("find_by_id", "missing")) == 2
        assert not any(k.endswith(":id:missing") for k in cache.store)

    @pytest.mark.asyncio
    async def test_find_many_caches_per_query(self, parts: Any) -> None:
        inner, cache, repo = parts
        await repo.find_many(status="active")
        await repo.find_many(status="active")
        await repo.find_many(status="other")
        assert inner.calls.count(("find_many", {"status": "active"})) == 1
        assert inner.calls.count(("find_many", {"status": "other"})) == 1

    @pytest.mark.asyncio
    async def test_count_cached(self, parts: Any) -> None:
        inner, cache, repo = parts
        assert await repo.count(status="active") == 1
        assert await repo.count(status="active") == 1
        assert inner.calls.count(("count", {"status": "active"})) == 1


class TestWriteInvalidation:
    @pytest.mark.asyncio
    async def test_create_invalidates_reads(self, parts: Any) -> None:
        inner, cache, repo = parts
        await repo.find_by_id("1")  # cached under version N
        await repo.create({"id": "2"})
        # Version bumped: the old cache key no longer resolves.
        assert await repo.find_by_id("1") is not None
        assert inner.calls.count(("find_by_id", "1")) == 2

    @pytest.mark.asyncio
    async def test_update_deletes_id_key_and_invalidates(self, parts: Any) -> None:
        inner, cache, repo = parts
        await repo.find_by_id("1")
        await repo.update({"id": "1", "name": "Bob"})
        assert any(k.endswith(":id:1") for k in cache.deleted)
        assert inner.calls.count(("find_by_id", "1")) == 1
        await repo.find_by_id("1")
        assert inner.calls.count(("find_by_id", "1")) == 2

    @pytest.mark.asyncio
    async def test_update_entity_without_id_still_invalidates(self, parts: Any) -> None:
        inner, cache, repo = parts
        await repo.find_by_id("1")
        await repo.update({"name": "no-id"})
        await repo.find_by_id("1")
        assert inner.calls.count(("find_by_id", "1")) == 2

    @pytest.mark.asyncio
    async def test_delete_by_id_invalidates(self, parts: Any) -> None:
        inner, cache, repo = parts
        await repo.find_by_id("1")
        assert await repo.delete_by_id("1") is True
        assert any(k.endswith(":id:1") for k in cache.deleted)
        await repo.find_by_id("1")
        assert inner.calls.count(("find_by_id", "1")) == 2


class TestProxying:
    @pytest.mark.asyncio
    async def test_unknown_methods_proxy_to_inner(self, parts: Any) -> None:
        inner, cache, repo = parts
        assert repo.custom_thing() == "proxied"


class TestHashing:
    @pytest.mark.asyncio
    async def test_version_key_defaults_to_one_and_persists(self, parts: Any) -> None:
        inner, cache, repo = parts
        assert repo._prefix == "users"
        assert await repo._get_version() == 1
        assert cache.store["users:__version__"] == 1
        # Re-reading hits the persisted version, not a fresh one.
        assert await repo._get_version() == 1

    def test_hash_kwargs_is_order_insensitive(self) -> None:
        from quadkit.sql.repositories.cached import _hash_kwargs  # noqa: PLC0415

        assert _hash_kwargs({"a": 1, "b": 2}) == _hash_kwargs({"b": 2, "a": 1})
        assert _hash_kwargs({"a": 1}) != _hash_kwargs({"a": 2})

    def test_hash_kwargs_uses_custom_hasher(self) -> None:
        from quadkit.sql.repositories.cached import _hash_kwargs  # noqa: PLC0415

        hasher = MagicMock()
        hasher.digest.return_value = "0123456789abcdef"
        assert _hash_kwargs({"a": 1}, hasher=hasher) == "0123456789ab"
        hasher.digest.assert_called_once()
