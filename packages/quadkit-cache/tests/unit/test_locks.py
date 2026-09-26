"""Tests for cache locks."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestAutoRenewingLock:
    """Tests for AutoRenewingLock."""

    def test_creation(self) -> None:
        """Test creating an AutoRenewingLock."""
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        lock = AutoRenewingLock(
            redis=mock_redis,
            key="test:lock",
            lock_id="lock-123",
            ttl=30,
        )
        
        assert lock._key == "test:lock"
        assert lock._lock_id == "lock-123"
        assert lock._ttl == 30
        assert lock._auto_renew is True
        assert lock._renew_interval == 10  # ttl // 3

    def test_creation_with_custom_renew_interval(self) -> None:
        """Test creating with custom renew interval."""
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        lock = AutoRenewingLock(
            redis=mock_redis,
            key="test:lock",
            lock_id="lock-123",
            ttl=30,
            renew_interval=5,
        )
        
        assert lock._renew_interval == 5

    def test_creation_with_auto_renew_disabled(self) -> None:
        """Test creating with auto_renew disabled."""
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        lock = AutoRenewingLock(
            redis=mock_redis,
            key="test:lock",
            lock_id="lock-123",
            ttl=30,
            auto_renew=False,
        )
        
        assert lock._auto_renew is False

    @pytest.mark.asyncio
    async def test_start_auto_renewal(self) -> None:
        """Test starting auto-renewal."""
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)
        
        lock = AutoRenewingLock(
            redis=mock_redis,
            key="test:lock",
            lock_id="lock-123",
            ttl=30,
        )
        
        await lock.start_auto_renewal()
        
        assert lock._renew_task is not None
        assert lock._acquired_at is not None

    @pytest.mark.asyncio
    async def test_start_auto_renewal_when_disabled(self) -> None:
        """Test starting auto-renewal when disabled does nothing."""
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        
        lock = AutoRenewingLock(
            redis=mock_redis,
            key="test:lock",
            lock_id="lock-123",
            ttl=30,
            auto_renew=False,
        )
        
        await lock.start_auto_renewal()
        
        assert lock._renew_task is None

    @pytest.mark.asyncio
    async def test_stop_auto_renewal(self) -> None:
        """Test stopping auto-renewal."""
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)
        
        lock = AutoRenewingLock(
            redis=mock_redis,
            key="test:lock",
            lock_id="lock-123",
            ttl=30,
        )
        
        await lock.start_auto_renewal()
        await lock.stop_auto_renewal()
        
        assert lock._stop_renew is True

    @pytest.mark.asyncio
    async def test_release(self) -> None:
        """Test releasing lock."""
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)
        
        lock = AutoRenewingLock(
            redis=mock_redis,
            key="test:lock",
            lock_id="lock-123",
            ttl=30,
        )
        
        await lock.start_auto_renewal()
        await lock.release()
        
        assert lock._stop_renew is True


class TestLockContextManager:
    """Tests for LockContextManager."""

    @pytest.mark.asyncio
    async def test_context_manager_acquires_lock(self) -> None:
        """Test context manager acquires lock successfully."""
        from quadkit.cache.locks.context import LockContextManager

        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.eval = AsyncMock(return_value=1)
        
        async with LockContextManager(
            redis=mock_redis,
            key="test:lock",
            ttl=30,
            auto_renew=True,
        ) as lock:
            assert lock is not None

    @pytest.mark.asyncio
    async def test_context_manager_raises_on_failure(self) -> None:
        """Test context manager raises when lock cannot be acquired."""
        from quadkit.cache.locks.context import LockContextManager
        from quadkit.cache.exceptions import LockAcquisitionError

        mock_redis = MagicMock()
        mock_redis.set = AsyncMock(return_value=False)
        
        with pytest.raises(LockAcquisitionError):
            async with LockContextManager(
                redis=mock_redis,
                key="test:lock",
                ttl=30,
                auto_renew=True,
            ):
                pass


class TestAutoRenewingLockEvalShape:
    """AutoRenewingLock must call redis.eval with (script, numkeys, *args).

    Regression: the previous code passed ``eval(script, [key], [lock_id,
    ttl])`` — a list as numkeys and one list as the single "key" — which
    corrupts the script arguments against real redis-py.
    """

    @pytest.mark.asyncio
    async def test_extend_lock_uses_positional_keys_and_args(self) -> None:
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)

        lock = AutoRenewingLock(
            redis=mock_redis,
            key="res:1",
            lock_id="owner:abc",
            ttl=30,
        )

        success = await lock._extend_lock()

        assert success is True
        script, numkeys, key, lock_id, ttl = mock_redis.eval.call_args.args
        assert numkeys == 1
        assert key == "res:1"
        assert lock_id == "owner:abc"
        assert ttl == "30"
        assert "EXPIRE" in script

    @pytest.mark.asyncio
    async def test_release_uses_positional_keys_and_args(self) -> None:
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=1)

        lock = AutoRenewingLock(
            redis=mock_redis,
            key="res:1",
            lock_id="owner:abc",
            ttl=30,
            auto_renew=False,
        )

        await lock.release()

        script, numkeys, key, lock_id = mock_redis.eval.call_args.args
        assert numkeys == 1
        assert key == "res:1"
        assert lock_id == "owner:abc"
        assert "DEL" in script

    @pytest.mark.asyncio
    async def test_extend_lock_failure_returns_false(self) -> None:
        from quadkit.cache.locks.auto_renewing import AutoRenewingLock

        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=0)

        lock = AutoRenewingLock(
            redis=mock_redis,
            key="res:1",
            lock_id="stale:abc",
            ttl=30,
        )

        assert (await lock._extend_lock()) is False
