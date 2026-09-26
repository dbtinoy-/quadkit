"""Tests for DistributedLockProtocol (Redis-backed lock with TTL renewal)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from quadkit.cache.exceptions import LockAcquisitionError
from quadkit.cache.locks.distributed import DistributedLockProtocol


class FakeRedis:
    """Minimal async Redis double: SET NX + EVAL script results."""

    def __init__(self, set_result: Any = True, eval_results: list[Any] | None = None) -> None:
        self.set_result = set_result
        self.eval_results = list(eval_results or [])
        self.set_calls: list[dict[str, Any]] = []
        self.eval_calls: list[tuple[Any, ...]] = []

    async def set(self, key: str, value: str, *, nx: bool, ex: int) -> Any:
        self.set_calls.append({"key": key, "value": value, "nx": nx, "ex": ex})
        return self.set_result

    async def eval(self, script: str, numkeys: int, *args: Any) -> Any:
        self.eval_calls.append((script, numkeys, *args))
        if self.eval_results:
            return self.eval_results.pop(0)
        return 1


@pytest.fixture
def redis() -> FakeRedis:
    return FakeRedis()


def _lock(redis: FakeRedis, **kwargs: Any) -> DistributedLockProtocol:
    return DistributedLockProtocol(redis, "my-lock", **kwargs)


class TestConstruction:
    def test_key_prefix_and_defaults(self, redis: FakeRedis) -> None:
        lock = _lock(redis)
        assert lock.key == "lock:my-lock"
        assert lock.ttl == 30
        assert lock.renewal_interval == 15  # TTL / DEFAULT divisor 2
        assert lock.owner  # uuid4 string

    def test_custom_ttl_and_renewal(self, redis: FakeRedis) -> None:
        lock = _lock(redis, ttl=10, renewal_interval=3)
        assert lock.renewal_interval == 3
        lock2 = _lock(redis, ttl=10)
        assert lock2.renewal_interval == 5

    def test_not_locked_initially(self, redis: FakeRedis) -> None:
        assert _lock(redis).is_locked is False
        assert _lock(redis).lock_info is None


class TestAcquire:
    async def test_acquire_success(self, redis: FakeRedis) -> None:
        lock = _lock(redis)
        assert await lock.acquire() is True
        assert lock.is_locked is True
        info = lock.lock_info
        assert info is not None
        assert info.key == "lock:my-lock"
        assert info.owner == lock.owner
        assert info.ttl == 30
        assert info.renewal_task is not None
        assert redis.set_calls[0]["nx"] is True
        assert redis.set_calls[0]["ex"] == 30
        assert redis.set_calls[0]["value"] == lock.owner
        await lock.release()

    async def test_acquire_contended_fails(self, redis: FakeRedis) -> None:
        redis.set_result = False
        lock = _lock(redis)
        assert await lock.acquire() is False
        assert lock.is_locked is False

    async def test_acquire_redis_error_degrades(self, redis: FakeRedis) -> None:
        async def boom(*a: Any, **kw: Any) -> Any:
            raise ConnectionError("redis down")

        redis.set = boom  # type: ignore[method-assign]
        lock = _lock(redis)
        assert await lock.acquire() is False


class TestRelease:
    async def test_release_owned(self, redis: FakeRedis) -> None:
        redis.eval_results = [1]
        lock = _lock(redis)
        await lock.acquire()
        assert await lock.release() is True
        assert lock.is_locked is False
        assert lock.lock_info is None
        # Release script called with key + owner.
        script, numkeys, key, owner = redis.eval_calls[-1]
        assert numkeys == 1
        assert key == "lock:my-lock"
        assert owner == lock.owner
        assert "DEL" in script

    async def test_release_not_held(self, redis: FakeRedis) -> None:
        redis.eval_results = [-1]
        lock = _lock(redis)
        await lock.acquire()
        assert await lock.release() is False

    async def test_release_not_owner(self, redis: FakeRedis) -> None:
        redis.eval_results = [0]
        lock = _lock(redis)
        await lock.acquire()
        assert await lock.release() is False

    async def test_release_error_degrades(self, redis: FakeRedis) -> None:
        lock = _lock(redis)
        await lock.acquire()

        async def boom(*a: Any, **kw: Any) -> Any:
            raise ConnectionError("redis down")

        redis.eval = boom  # type: ignore[method-assign]
        assert await lock.release() is False

    async def test_release_cancels_renewal_task(self, redis: FakeRedis) -> None:
        lock = _lock(redis, ttl=1000, renewal_interval=999)
        await lock.acquire()
        task = lock.lock_info.renewal_task
        assert task is not None
        assert not task.cancelled()
        await lock.release()
        assert task.cancelled()


class TestRenewal:
    async def test_renewal_extends_and_stops_when_lost(self) -> None:
        # renewal_interval tiny → loop ticks quickly; first eval=1 (renewed),
        # second eval=0 (not owner → break out of loop).
        redis = FakeRedis(eval_results=[1, 0])
        lock = _lock(redis, ttl=100, renewal_interval=0.01)
        await lock.acquire()
        await asyncio.sleep(0.05)
        assert lock.lock_info is not None  # release never called
        assert len(redis.eval_calls) >= 2
        await lock.release()

    async def test_renewal_cancellation_clean(self) -> None:
        redis = FakeRedis(eval_results=[1])
        lock = _lock(redis, ttl=100, renewal_interval=0.01)
        await lock.acquire()
        task = lock.lock_info.renewal_task
        await asyncio.sleep(0.02)
        await lock.release()
        # Release cancels the renewal task; cancellation is clean.
        assert task is not None
        assert task.cancelled()

    async def test_renewal_error_is_swallowed(self) -> None:
        redis = FakeRedis(eval_results=[1])
        lock = _lock(redis, ttl=100, renewal_interval=0.01)
        await lock.acquire()

        async def boom(*a: Any, **kw: Any) -> Any:
            raise ConnectionError("redis down")

        redis.eval = boom  # type: ignore[method-assign]
        await asyncio.sleep(0.05)
        # Renewal task terminated with the error, but lock object is intact
        # and the done-callback surfaced the exception via logger (no raise).
        task = lock.lock_info.renewal_task
        assert task is not None
        assert task.done()
        await lock.release()


class TestLockContextManager:
    async def test_happy_path_releases_on_exit(self, redis: FakeRedis) -> None:
        redis.eval_results = [1]
        lock = _lock(redis)
        async with lock.lock():
            assert lock.is_locked is True
        assert lock.is_locked is False

    async def test_raises_when_not_acquired(self, redis: FakeRedis) -> None:
        redis.set_result = False
        lock = _lock(redis)
        with pytest.raises(LockAcquisitionError, match="Could not acquire"):
            async with lock.lock():
                pass  # pragma: no cover

    async def test_releases_even_on_body_error(self, redis: FakeRedis) -> None:
        redis.eval_results = [1]
        lock = _lock(redis)
        with pytest.raises(RuntimeError, match="boom"):
            async with lock.lock():
                raise RuntimeError("boom")
        assert lock.is_locked is False
