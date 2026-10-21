"""The reporting surface admin dashboards read from a cache service.

Applications ship an admin cache dashboard; it needs the service's own
counters, the backend's counters (hits/misses/evictions/entries), the key
prefix and the default TTL. Asking for those through private attributes is
what this surface exists to avoid — and the eviction count in particular used
to be invisible: the store dropped the least-recently-used entry while the
backend reported ``evictions: 0``, so a full cache looked idle.
"""

from __future__ import annotations

import pytest

from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.config.operation import CacheOperationConfig
from quadkit.cache.service.core import CacheService


def _service(**kwargs: object) -> CacheService:
    config = CacheOperationConfig(default_ttl=60, key_prefix="gw:test:")
    return CacheService(
        backend=MemoryCacheBackend(config=config, max_size=3), **kwargs
    )


def test_service_exposes_backend_prefix_and_ttl() -> None:
    """Reporting reads the configuration through public properties."""
    service = _service()
    assert isinstance(service.backend, MemoryCacheBackend)
    assert service.key_prefix == "gw:test:"
    assert service.default_ttl == 60


def test_service_adopts_the_backend_config_when_none_is_given() -> None:
    """A backend-injected service reports the configuration it delegates to."""
    config = CacheOperationConfig(default_ttl=15, key_prefix="gw:x:")
    service = CacheService(backend=MemoryCacheBackend(config=config))
    assert service.key_prefix == "gw:x:"
    assert service.default_ttl == 15


def test_explicit_service_config_wins() -> None:
    """A caller-supplied service config is not overwritten by the backend's."""
    config = CacheOperationConfig(default_ttl=15, key_prefix="gw:x:")
    service = CacheService(
        config=CacheOperationConfig(default_ttl=5, key_prefix="gw:y:"),
        backend=MemoryCacheBackend(config=config),
    )
    assert service.key_prefix == "gw:y:"
    assert service.default_ttl == 5


def test_backend_stats_are_counted_from_real_operations() -> None:
    """Hits, misses and entries come from the operations that happened."""
    service = _service()

    async def _exercise() -> None:
        await service.set("hit", "value")
        assert await service.get("hit") == "value"
        assert await service.get("absent") is None

    asyncio_run(_exercise())
    stats = service.get_backend_stats()
    assert stats == {"hits": 1, "misses": 1, "evictions": 0, "entries": 1}


def test_backend_stats_reports_store_evictions() -> None:
    """Filling past capacity is visible to the dashboard as evictions."""
    service = _service()

    async def _fill() -> None:
        for index in range(6):
            await service.set(f"key-{index}", index)

    asyncio_run(_fill())
    stats = service.get_backend_stats()
    assert stats["entries"] == 3
    assert stats["evictions"] == 3


def test_backend_stats_are_zeroed_when_the_backend_cannot_report() -> None:
    """A backend without counters yields zeros, never fabricated activity."""

    class _Opaque:
        async def get(self, key: str) -> None:
            return None

    service = CacheService(backend=_Opaque())
    assert service.get_backend_stats() == {
        "hits": 0,
        "misses": 0,
        "evictions": 0,
        "entries": 0,
    }


def test_backend_stats_never_raise() -> None:
    """A backend whose stats blow up reports zeros instead of failing a page."""

    class _Exploding(MemoryCacheBackend):
        def get_stats(self):
            raise RuntimeError("stats unavailable")

    service = CacheService(backend=_Exploding(max_size=1))
    assert service.get_backend_stats()["entries"] == 0


def test_reset_stats_clears_evictions_too() -> None:
    """Resetting counters clears the store's eviction count as well."""
    service = _service()

    async def _fill() -> None:
        for index in range(6):
            await service.set(f"key-{index}", index)

    asyncio_run(_fill())
    assert service.get_backend_stats()["evictions"] == 3

    service.backend.reset_stats()  # type: ignore[union-attr]
    assert service.get_backend_stats()["evictions"] == 0


def asyncio_run(coro) -> None:
    """Run a coroutine to completion without pytest-asyncio ceremony."""
    import asyncio

    asyncio.run(coro)


@pytest.mark.parametrize("key_prefix", ["", "gw:user:"])
def test_prefix_round_trips_through_the_service(key_prefix: str) -> None:
    """The reported prefix is the one keys are actually built with."""
    config = CacheOperationConfig(key_prefix=key_prefix)
    service = CacheService(backend=MemoryCacheBackend(config=config))
    assert service.key_prefix == key_prefix
