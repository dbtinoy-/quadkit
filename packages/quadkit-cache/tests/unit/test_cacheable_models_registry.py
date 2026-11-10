"""Tests for @cacheable(..., models=(...,)) auto-registration and JSON round-trip."""

from __future__ import annotations

from dataclasses import dataclass
import fnmatch

import pytest

from quadkit.cache.decorators import cache_evict, cacheable
from quadkit.domain import DomainModel
from quadkit.result import Err, Ok, Result
from quadkit.serialization import dumps_str, loads
from quadkit.validation import ConfigDict, computed_field


@dataclass(init=False, eq=False, kw_only=True)
class _CachedBreed(DomainModel):
    model_config = ConfigDict(extra="allow", from_attributes=True)

    id: str
    pet_type_id: str
    name: str

    @computed_field
    @property
    def species(self) -> str:
        return self.pet_type_id


class _JsonRedisLikeBackend:
    """Backend simulating Redis JSON string serialization so warm hits exercise decoding."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> Ok[object | None]:
        raw = self._store.get(key)
        if raw is None:
            return Ok(None)
        return Ok(loads(raw))

    async def set(self, key: str, value: object, ttl: int | None = None) -> Ok[bool]:
        _ = ttl
        self._store[key] = dumps_str(value)
        return Ok(True)

    async def delete_pattern(self, pattern: str) -> Ok[int]:
        matched = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in matched:
            del self._store[k]
        return Ok(len(matched))


@pytest.mark.asyncio
async def test_cacheable_models_kwarg_registers_and_rehydrates_list_over_json() -> None:
    """@cacheable(..., models=(...,)) registers DomainModel types for warm JSON hits."""
    backend = _JsonRedisLikeBackend()
    compute_calls = 0

    class BreedCatalogService:
        def __init__(self) -> None:
            self._cache = backend

        @cacheable(ttl=60, key_prefix="breed", models=(_CachedBreed,))
        async def list_breeds(self, color: str) -> Ok[list[_CachedBreed]]:
            nonlocal compute_calls
            compute_calls += 1
            return Ok(
                [
                    _CachedBreed(
                        id="dog_golden_retriever",
                        pet_type_id="dog",
                        name=f"{color} Retriever",
                    )
                ]
            )

    svc = BreedCatalogService()
    cold = await svc.list_breeds("Golden")
    warm = await svc.list_breeds("Golden")

    assert compute_calls == 1
    assert cold.is_ok()
    assert warm.is_ok()
    warm_items = warm.unwrap()
    assert len(warm_items) == 1
    assert isinstance(warm_items[0], _CachedBreed)
    assert warm_items[0].species == "dog"
    assert warm_items[0].name == "Golden Retriever"


@pytest.mark.asyncio
async def test_cacheable_dict_roundtrip_and_cache_evict_skips_err() -> None:
    """@cacheable rehydrates dict[str, DomainModel] and @cache_evict invalidates only on Ok."""
    backend = _JsonRedisLikeBackend()
    loads_count = 0

    class BreedMapService:
        def __init__(self) -> None:
            self._cache = backend
            self._name = "Shiba Inu"

        @cacheable(ttl=60, key_prefix="breed_map", models=(_CachedBreed,))
        async def get_by_ids(self, ids: tuple[str, ...]) -> Ok[dict[str, _CachedBreed]]:
            nonlocal loads_count
            loads_count += 1
            return Ok(
                {
                    bid: _CachedBreed(id=bid, pet_type_id="dog", name=self._name)
                    for bid in ids
                }
            )

        @cache_evict("breed_map:*")
        async def update_breed(
            self, new_name: str, *, fail: bool = False
        ) -> Result[bool, str]:
            if fail:
                return Err("write_failed")
            self._name = new_name
            return Ok(True)

    svc = BreedMapService()
    first = (await svc.get_by_ids(("shiba",))).unwrap()
    second = (await svc.get_by_ids(("shiba",))).unwrap()
    assert loads_count == 1
    assert isinstance(second["shiba"], _CachedBreed)
    assert second["shiba"].name == "Shiba Inu"

    # Failed write must NOT evict warm cache
    failed = await svc.update_breed("Broken", fail=True)
    assert failed.is_err()
    still_warm = (await svc.get_by_ids(("shiba",))).unwrap()
    assert loads_count == 1
    assert still_warm["shiba"].name == "Shiba Inu"

    # Successful write evicts pattern so next read recomputes
    updated = await svc.update_breed("Akita Inu")
    assert updated.is_ok()
    refreshed = (await svc.get_by_ids(("shiba",))).unwrap()
    assert loads_count == 2
    assert isinstance(refreshed["shiba"], _CachedBreed)
    assert refreshed["shiba"].name == "Akita Inu"


@pytest.mark.asyncio
async def test_cacheable_negative_caches_bare_none_return_value() -> None:
    """@cacheable caches bare None return values instead of missing on every call."""
    backend = _JsonRedisLikeBackend()
    db_queries = 0

    class SubscriptionLookupService:
        def __init__(self) -> None:
            self._cache = backend

        @cacheable(ttl=120, key_prefix="user_sub")
        async def get_user_subscription(self, user_id: str) -> dict[str, str] | None:
            nonlocal db_queries
            db_queries += 1
            if user_id == "paid-user":
                return {"plan": "plus"}
            return None

        @cache_evict("user_sub:*")
        async def invalidate_subscriptions(self) -> None:
            return None

    svc = SubscriptionLookupService()
    assert await svc.get_user_subscription("free-user") is None
    assert await svc.get_user_subscription("free-user") is None
    assert await svc.get_user_subscription("free-user") is None
    assert db_queries == 1

    await svc.invalidate_subscriptions()
    assert await svc.get_user_subscription("free-user") is None
    assert db_queries == 2
