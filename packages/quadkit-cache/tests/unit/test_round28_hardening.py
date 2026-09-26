"""Round 28 hardening pins.

Covers the gap-hunt fixes from the quadkit-cache audit: the
Result-returning cache API promised ``Err(CacheError)`` on *any*
backend failure, but the except tuples only covered builtin error
types — driver-specific errors (redis-py's RedisError hierarchy,
memcached errors) are pure-Exception subclasses and escaped as raw
exceptions. Same for the cleanup/shutdown/health/metrics loops, where
a foreign error killed the loop or skipped the remaining items.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class _DriverError(Exception):
    """Stand-in for driver errors (e.g. redis.exceptions.ConnectionError),
    which are NOT OSError/ConnectionError/RuntimeError/ValueError/TypeError."""


def _redis_backend(store_error: type[Exception]) -> Any:
    from quadkit.cache.backends.redis.backend import RedisCacheBackend

    store = MagicMock()
    store.get = AsyncMock(side_effect=store_error("backend exploded"))
    store.set = AsyncMock(side_effect=store_error("backend exploded"))
    store.delete = AsyncMock(side_effect=store_error("backend exploded"))
    return RedisCacheBackend(store=store)


class TestRedisBackendResultContract:
    @pytest.mark.asyncio
    async def test_get_driver_error_returns_err(self) -> None:
        backend = _redis_backend(_DriverError)

        result = await backend.get("k")  # must not raise

        assert result.is_err()
        assert "backend exploded" in str(result.unwrap_err())

    @pytest.mark.asyncio
    async def test_set_driver_error_returns_err(self) -> None:
        backend = _redis_backend(_DriverError)

        result = await backend.set("k", "v")  # must not raise

        assert result.is_err()
        assert "backend exploded" in str(result.unwrap_err())

    @pytest.mark.asyncio
    async def test_delete_driver_error_returns_err(self) -> None:
        backend = _redis_backend(_DriverError)

        result = await backend.delete("k")  # must not raise

        assert result.is_err()


class TestMemoryKVCleanupSurvival:
    @pytest.mark.asyncio
    async def test_cleanup_task_survives_foreign_error(self) -> None:
        from quadkit.cache.backends.memory.kv import InMemoryStorage

        storage = InMemoryStorage(cleanup_interval=0.01)
        ticks: list[float] = []
        second_tick = asyncio.Event()

        async def _bad_cleanup() -> None:
            ticks.append(1.0)
            if len(ticks) >= 2:
                second_tick.set()
            raise KeyError("cleanup exploded")

        storage._cleanup_expired = _bad_cleanup  # type: ignore[method-assign]
        storage._connected = True
        task = asyncio.create_task(storage._periodic_cleanup())
        try:
            await asyncio.wait_for(second_tick.wait(), timeout=1.0)
        finally:
            storage._connected = False
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # The loop must keep ticking across foreign errors.
        assert len(ticks) >= 2


class TestTieredShutdown:
    @pytest.mark.asyncio
    async def test_all_tiers_closed_despite_foreign_error(self) -> None:
        from quadkit.cache.strategies.tiered import TieredCache

        cache = TieredCache.__new__(TieredCache)

        l1 = MagicMock()
        l1.close = AsyncMock(side_effect=KeyError("l1 close exploded"))
        l2 = MagicMock()
        l2.close = AsyncMock()

        service = MagicMock()
        service.get_backend = MagicMock(side_effect=[l1, l2])
        cache.cache_service = service  # type: ignore[attr-defined]
        cache.l1_backend = "l1"  # type: ignore[attr-defined]
        cache.l2_backend = "l2"  # type: ignore[attr-defined]

        await cache.shutdown()  # must not raise

        l1.close.assert_awaited_once()
        l2.close.assert_awaited_once()
