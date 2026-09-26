"""Tests for memory lock store."""

import pytest
import time

from quadkit.cache.backends.memory_lock import MemoryLockStore


class TestMemoryLockStore:
    """Tests for MemoryLockStore."""

    @pytest.fixture
    def store(self):
        return MemoryLockStore()

    @pytest.mark.asyncio
    async def test_acquire_lock(self, store):
        """Should acquire a lock."""
        result = await store.acquire("test-lock", "owner1", ttl=10)
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_lock_already_held(self, store):
        """Should fail to acquire already held lock."""
        await store.acquire("test-lock", "owner1", ttl=10)
        result = await store.acquire("test-lock", "owner2", ttl=10)
        assert result is False

    @pytest.mark.asyncio
    async def test_release_lock(self, store):
        """Should release a lock."""
        await store.acquire("test-lock", "owner1", ttl=10)
        result = await store.release("test-lock", "owner1")
        assert result is True
        assert await store.is_locked("test-lock") is False

    @pytest.mark.asyncio
    async def test_release_other_owners_lock(self, store):
        """Should not release lock owned by another."""
        await store.acquire("test-lock", "owner1", ttl=10)
        result = await store.release("test-lock", "owner2")
        assert result is False
        assert await store.is_locked("test-lock") is True

    @pytest.mark.asyncio
    async def test_release_nonexistent_lock(self, store):
        """Should return False when releasing nonexistent lock."""
        result = await store.release("nonexistent", "owner1")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_locked_false_for_nonexistent(self, store):
        """Should return False for nonexistent lock."""
        result = await store.is_locked("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_locked_true_when_held(self, store):
        """Should return True when lock is held."""
        await store.acquire("test-lock", "owner1", ttl=10)
        result = await store.is_locked("test-lock")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_locked_false_after_expiry(self, store):
        """Should return False after lock expires."""
        await store.acquire("test-lock", "owner1", ttl=0)
        await asyncio.sleep(0.01)
        result = await store.is_locked("test-lock")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check(self, store):
        """Should return healthy status."""
        result = await store.health_check()
        
        assert result.status.value == "healthy"
        assert result.component == "memory-lock"
        assert "locks_count" in result.details


import asyncio
