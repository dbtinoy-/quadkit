# packages/quadkit-cache/tests/unit/test_lock_renewal.py

import asyncio
from unittest.mock import AsyncMock

import pytest

from quadkit.cache.exceptions import LockAcquisitionError
from quadkit.cache.locks import DistributedLockProtocol, LockManager


@pytest.fixture
def redis_client():
    """Mock Redis client for testing with in-memory store."""
    store: dict = {}
    client = AsyncMock()

    async def mock_set(key, value, *, nx=False, ex=None):
        if nx and key in store:
            return None
        store[key] = value
        return True

    async def mock_get(key):
        return store.get(key)

    async def mock_delete(*keys):
        for key in keys:
            store.pop(key, None)
        return len(keys)

    client.set = AsyncMock(side_effect=mock_set)
    client.get = AsyncMock(side_effect=mock_get)
    client.delete = AsyncMock(side_effect=mock_delete)
    client.expire.return_value = 1
    client.eval.return_value = 1
    return client


class TestLockAcquisition:
    """Test lock acquisition and release via LockManager."""

    @pytest.mark.asyncio
    async def test_create_lock_returns_distributed_lock(self, redis_client):
        """LockManager.create_lock returns a DistributedLockProtocol instance."""
        manager = LockManager(redis_client)
        lock = manager.create_lock("test_key")
        assert isinstance(lock, DistributedLockProtocol)

    @pytest.mark.asyncio
    async def test_lock_acquired_sets_lock_info(self, redis_client):
        """Acquiring a lock populates _lock_info."""
        lock = DistributedLockProtocol(redis_client, key="test_lock", ttl=30)
        acquired = await lock.acquire()

        assert acquired is True
        assert lock._lock_info is not None
        assert lock.is_locked

        await lock.release()

    @pytest.mark.asyncio
    async def test_lock_context_manager_acquires_and_releases(self, redis_client):
        """lock.lock() context manager acquires on enter, releases on exit."""
        lock = DistributedLockProtocol(redis_client, key="test_lock", ttl=30)

        async with lock.lock():
            assert lock.is_locked

        assert not lock.is_locked

    @pytest.mark.asyncio
    async def test_lock_context_manager_raises_when_not_acquired(self):
        """lock.lock() raises LockAcquisitionError when Redis rejects acquisition."""
        failing_redis = AsyncMock()
        failing_redis.set.return_value = None  # Simulate acquisition failure

        lock = DistributedLockProtocol(failing_redis, key="test_lock", ttl=30)

        with pytest.raises(LockAcquisitionError):
            async with lock.lock():
                pass  # Should never reach here


class TestLockRenewal:
    """Test lock auto-renewal background task."""

    @pytest.mark.asyncio
    async def test_renewal_task_created_on_acquire(self, redis_client):
        """Acquiring lock starts a background renewal task."""
        lock = DistributedLockProtocol(redis_client, key="test_lock", ttl=30)
        await lock.acquire()

        assert lock._lock_info is not None
        assert lock._lock_info.renewal_task is not None
        assert not lock._lock_info.renewal_task.done()

        await lock.release()

    @pytest.mark.asyncio
    async def test_renewal_task_stops_on_release(self, redis_client):
        """Releasing lock cancels the renewal task."""
        lock = DistributedLockProtocol(redis_client, key="test_lock", ttl=30)
        await lock.acquire()
        renewal_task = lock._lock_info.renewal_task  # type: ignore[union-attr]

        await lock.release()

        assert renewal_task.done()

    @pytest.mark.asyncio
    async def test_renewal_calls_eval_with_extend_script(self, redis_client):
        """Renewal extends the TTL atomically via the compare-and-expire script."""
        lock = DistributedLockProtocol(redis_client, key="test_key", ttl=4, renewal_interval=1)
        await lock.acquire()

        await asyncio.sleep(2.2)  # Allow 2 renewals

        renew_calls = [
            call
            for call in redis_client.eval.call_args_list
            if call.args and call.args[0] == DistributedLockProtocol.LUA_EXTEND_LOCK
        ]
        assert len(renew_calls) >= 2, (
            f"Expected >=2 renewals, got {len(renew_calls)}"
        )
        # (script, numkeys, key, owner, ttl)
        script, numkeys, key, owner, ttl = renew_calls[0].args
        assert script == DistributedLockProtocol.LUA_EXTEND_LOCK
        assert numkeys == 1
        assert key == f"{lock.key}"
        assert owner == lock.owner
        assert ttl == "4"

        await lock.release()


class TestLockManagerReleaseAll:
    """Test LockManager.release_all."""

    @pytest.mark.asyncio
    async def test_release_all_releases_managed_locks(self, redis_client):
        """release_all() triggers release on all acquired locks."""
        manager = LockManager(redis_client)
        lock_a = manager.create_lock("key_a")
        lock_b = manager.create_lock("key_b")

        await lock_a.acquire()
        await lock_b.acquire()

        assert lock_a.is_locked
        assert lock_b.is_locked

        await manager.release_all()

        assert not lock_a.is_locked
        assert not lock_b.is_locked
