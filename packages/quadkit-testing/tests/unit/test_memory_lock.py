"""Tests for the in-memory lock implementations (memory/lock.py)."""

from __future__ import annotations

import asyncio

import pytest

from quadkit.contracts.core.lock import DistributedLockProtocol, LockInfo
from quadkit.contracts.exceptions.components import LockAcquisitionError
from quadkit.testing.memory.lock import (
    InMemoryAsyncLock,
    InMemoryDistributedLock,
    InMemoryLockStore,
)


@pytest.fixture
def store() -> InMemoryLockStore:
    return InMemoryLockStore()


class TestInMemoryDistributedLock:
    @pytest.mark.asyncio
    async def test_conforms_to_distributed_lock_protocol(self, store) -> None:
        lock = InMemoryDistributedLock("res", store=store)
        assert isinstance(lock, DistributedLockProtocol)

    @pytest.mark.asyncio
    async def test_acquire_release_cycle(self, store) -> None:
        lock = InMemoryDistributedLock("res", store=store)
        assert await lock.acquire() is True
        assert await lock.is_held() is True
        assert await lock.release() is True
        assert await lock.is_held() is False

    @pytest.mark.asyncio
    async def test_second_holder_cannot_acquire(self, store) -> None:
        a = InMemoryDistributedLock("res", holder_id="a", store=store)
        b = InMemoryDistributedLock("res", holder_id="b", store=store)
        assert await a.acquire() is True
        assert await b.acquire() is False
        assert await b.is_held() is False

    @pytest.mark.asyncio
    async def test_expired_lock_can_be_stolen(self, store) -> None:
        a = InMemoryDistributedLock("res", ttl=0.05, holder_id="a", store=store)
        b = InMemoryDistributedLock("res", ttl=10, holder_id="b", store=store)
        assert await a.acquire()
        await asyncio.sleep(0.06)
        assert await b.acquire() is True
        assert await b.is_held() is True

    @pytest.mark.asyncio
    async def test_release_by_non_holder_fails(self, store) -> None:
        a = InMemoryDistributedLock("res", holder_id="a", store=store)
        b = InMemoryDistributedLock("res", holder_id="b", store=store)
        assert await a.acquire()
        assert await b.release() is False

    @pytest.mark.asyncio
    async def test_release_unheld_returns_false(self, store) -> None:
        lock = InMemoryDistributedLock("res", store=store)
        assert await lock.release() is False

    @pytest.mark.asyncio
    async def test_is_held_false_after_expiry(self, store) -> None:
        lock = InMemoryDistributedLock("res", ttl=0.02, store=store)
        assert await lock.acquire()
        await asyncio.sleep(0.04)
        assert await lock.is_held() is False

    @pytest.mark.asyncio
    async def test_is_held_false_after_force_release(self, store) -> None:
        lock = InMemoryDistributedLock("res", store=store)
        assert await lock.acquire()
        await InMemoryDistributedLock.force_release("res", store=store)
        assert await lock.is_held() is False

    @pytest.mark.asyncio
    async def test_is_held_false_after_lock_stolen(self, store) -> None:
        a = InMemoryDistributedLock("res", ttl=0.05, holder_id="a", store=store)
        b = InMemoryDistributedLock("res", ttl=10, holder_id="b", store=store)
        assert await a.acquire()
        await asyncio.sleep(0.06)
        assert await b.acquire() is True  # steals the expired lock
        # `a` still believes it holds the lock, but the store disagrees.
        assert await a.is_held() is False

    @pytest.mark.asyncio
    async def test_extend_by_holder_and_non_holder(self, store) -> None:
        a = InMemoryDistributedLock("res", holder_id="a", store=store)
        b = InMemoryDistributedLock("res", holder_id="b", store=store)
        assert await a.acquire()
        assert await b.extend(5) is False
        assert await a.extend(5) is True

    @pytest.mark.asyncio
    async def test_acquire_blocking_succeeds_after_release(self, store) -> None:
        a = InMemoryDistributedLock("res", holder_id="a", store=store)
        b = InMemoryDistributedLock("res", holder_id="b", store=store)
        assert await a.acquire()
        task = asyncio.create_task(b.acquire_blocking(timeout=5))
        await asyncio.sleep(0.2)
        assert await a.release()
        assert await task is True

    @pytest.mark.asyncio
    async def test_acquire_blocking_times_out(self, store) -> None:
        a = InMemoryDistributedLock("res", holder_id="a", store=store)
        b = InMemoryDistributedLock("res", holder_id="b", store=store)
        assert await a.acquire()
        assert await b.acquire_blocking(timeout=0.25) is False

    @pytest.mark.asyncio
    async def test_context_manager_releases_on_exit(self, store) -> None:
        lock = InMemoryDistributedLock("res", store=store)
        async with lock:
            assert await lock.is_held() is True
        assert await lock.is_held() is False

    @pytest.mark.asyncio
    async def test_context_manager_contended_raises(self, store) -> None:
        a = InMemoryDistributedLock("res", holder_id="a", store=store)
        b = InMemoryDistributedLock("res", holder_id="b", store=store)
        assert await a.acquire()
        with pytest.raises(LockAcquisitionError, match="res"):
            async with b:
                pass  # pragma: no cover — never reached

    def test_holder_id_defaults_are_unique(self, store) -> None:
        first = InMemoryDistributedLock("res", store=store)
        second = InMemoryDistributedLock("res", store=store)
        assert first.holder_id != second.holder_id

    @pytest.mark.asyncio
    async def test_get_info(self, store) -> None:
        lock = InMemoryDistributedLock("res", holder_id="h", store=store)
        assert lock.get_info() is None
        await lock.acquire()
        info = lock.get_info()
        assert isinstance(info, LockInfo)
        assert info.resource == "res"
        assert info.holder == "h"

    @pytest.mark.asyncio
    async def test_force_release(self, store) -> None:
        lock = InMemoryDistributedLock("res", holder_id="a", store=store)
        await lock.acquire()
        assert await InMemoryDistributedLock.force_release("res", store=store) is True
        assert await InMemoryDistributedLock.force_release("res", store=store) is False

    @pytest.mark.asyncio
    async def test_get_all_locks_skips_expired(self, store) -> None:
        live = InMemoryDistributedLock("live", holder_id="a", ttl=60, store=store)
        dead = InMemoryDistributedLock("dead", holder_id="b", ttl=0.01, store=store)
        assert await live.acquire()
        assert await dead.acquire()
        await asyncio.sleep(0.03)
        locks = InMemoryDistributedLock.get_all_locks(store=store)
        assert list(locks) == ["live"]
        assert locks["live"].holder == "a"


class TestInMemoryAsyncLock:
    @pytest.mark.asyncio
    async def test_acquire_release_locked(self) -> None:
        lock = InMemoryAsyncLock()
        assert lock.locked() is False
        assert await lock.acquire() is True
        assert lock.locked() is True
        lock.release()
        assert lock.locked() is False

    @pytest.mark.asyncio
    async def test_release_without_acquire_raises(self) -> None:
        lock = InMemoryAsyncLock()
        with pytest.raises(RuntimeError):
            lock.release()

    @pytest.mark.asyncio
    async def test_context_manager_releases_on_error(self) -> None:
        lock = InMemoryAsyncLock()
        with pytest.raises(ValueError, match="boom"):
            async with lock:
                raise ValueError("boom")
        assert lock.locked() is False

    @pytest.mark.asyncio
    async def test_blocks_until_released(self) -> None:
        lock = InMemoryAsyncLock()
        assert await lock.acquire()

        task = asyncio.create_task(lock.acquire())
        await asyncio.sleep(0.05)
        assert not task.done()
        lock.release()
        assert await task is True
