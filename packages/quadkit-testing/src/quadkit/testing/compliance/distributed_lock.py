from __future__ import annotations

"""Contract compliance suite for DistributedLockProtocol implementations."""

import abc
from typing import Any

import pytest

__all__ = ["DistributedLockCompliance"]


class DistributedLockCompliance(abc.ABC):
    """Compliance suite for DistributedLockProtocol implementations.

    Subclass and implement create_lock() to run all compliance tests.
    """

    @abc.abstractmethod
    async def create_lock(self, key: str) -> Any:
        """Create a DistributedLockProtocol implementation under test.

        Args:
            key: Unique resource key for the lock.

        Returns:
            A fresh DistributedLockProtocol instance.
        """
        ...

    @pytest.mark.asyncio
    async def test_acquire_returns_true(self) -> None:
        """acquire() returns True when the lock is free."""
        lock = await self.create_lock("test-acquire")
        result = await lock.acquire()
        assert result is True
        await lock.release()

    @pytest.mark.asyncio
    async def test_release_returns_true_when_held(self) -> None:
        """release() returns True when the lock is currently held."""
        lock = await self.create_lock("test-release")
        await lock.acquire()
        result = await lock.release()
        assert result is True

    @pytest.mark.asyncio
    async def test_is_held_after_acquire(self) -> None:
        """is_held() returns True after acquire()."""
        lock = await self.create_lock("test-is-held")
        await lock.acquire()
        assert await lock.is_held() is True
        await lock.release()

    @pytest.mark.asyncio
    async def test_is_not_held_after_release(self) -> None:
        """is_held() returns False after release()."""
        lock = await self.create_lock("test-not-held")
        await lock.acquire()
        await lock.release()
        assert await lock.is_held() is False

    @pytest.mark.asyncio
    async def test_acquire_exclusive(self) -> None:
        """Second acquire() on the same key returns False while held."""
        lock_a = await self.create_lock("test-exclusive")
        lock_b = await self.create_lock("test-exclusive")
        await lock_a.acquire()
        result = await lock_b.acquire()
        assert result is False
        await lock_a.release()

    @pytest.mark.asyncio
    async def test_acquire_after_release(self) -> None:
        """acquire() returns True again after lock is released."""
        lock = await self.create_lock("test-reacquire")
        await lock.acquire()
        await lock.release()
        result = await lock.acquire()
        assert result is True
        await lock.release()

    @pytest.mark.asyncio
    async def test_context_manager_acquires_and_releases(self) -> None:
        """Context manager acquires on entry and releases on exit."""
        lock = await self.create_lock("test-ctx-manager")
        async with lock:
            assert await lock.is_held() is True
        assert await lock.is_held() is False

    @pytest.mark.asyncio
    async def test_extend_returns_true_when_held(self) -> None:
        """extend() returns True when the lock is currently held."""
        lock = await self.create_lock("test-extend")
        await lock.acquire()
        result = await lock.extend(10.0)
        assert result is True
        await lock.release()

    @pytest.mark.asyncio
    async def test_extend_returns_false_when_not_held(self) -> None:
        """extend() returns False when the lock is not held."""
        lock = await self.create_lock("test-extend-no-hold")
        result = await lock.extend(10.0)
        assert result is False

    @pytest.mark.asyncio
    async def test_acquire_blocking_succeeds(self) -> None:
        """acquire_blocking() returns True when the lock is free."""
        lock = await self.create_lock("test-blocking")
        result = await lock.acquire_blocking(timeout=2.0)
        assert result is True
        await lock.release()
