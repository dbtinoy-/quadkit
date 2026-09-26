"""Tests for in-memory storage (kv)."""

from __future__ import annotations

import pytest
import asyncio

from quadkit.primitives import clock as ambient_clock
from quadkit.cache.backends.memory.kv import InMemoryStorage
from quadkit.contracts.infra.storage import StorageType
from quadkit.testing.clock import FixedClock


class TestInMemoryStorage:
    """Tests for InMemoryStorage."""

    @pytest.fixture
    def storage(self):
        return InMemoryStorage(max_size=100, default_ttl=60)

    @pytest.fixture(autouse=True)
    def setup_clock(self):
        fixed = FixedClock()
        with ambient_clock.use(fixed):
            yield

    @pytest.mark.asyncio
    async def test_storage_type(self, storage):
        """Should return MEMORY storage type."""
        assert storage.storage_type == StorageType.MEMORY

    @pytest.mark.asyncio
    async def test_connect(self, storage):
        """Should connect and start cleanup task."""
        await storage.connect()
        assert storage._connected is True
        assert storage._cleanup_task is not None

    @pytest.mark.asyncio
    async def test_disconnect(self, storage):
        """Should disconnect and stop cleanup task."""
        await storage.connect()
        await storage.disconnect()
        assert storage._connected is False

    @pytest.mark.asyncio
    async def test_set_and_get(self, storage):
        """Should store and retrieve values."""
        await storage.set("key1", "value1")
        result = await storage.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, storage):
        """Should return None for nonexistent key."""
        result = await storage.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_namespace(self, storage):
        """Should store in specific namespace."""
        await storage.set("key1", "value1", namespace="ns1")
        result = await storage.get("key1", namespace="ns1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_set_with_ttl(self, storage):
        """Should store with TTL."""
        await storage.set("key1", "value1", ttl=1)
        result = await storage.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_delete_existing(self, storage):
        """Should delete existing key."""
        await storage.set("key1", "value1")
        result = await storage.delete("key1")
        assert result is True
        assert await storage.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        """Should return False for nonexistent key."""
        result = await storage.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, storage):
        """Should return True for existing key."""
        await storage.set("key1", "value1")
        result = await storage.exists("key1")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, storage):
        """Should return False for nonexistent key."""
        result = await storage.exists("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_keys_all(self, storage):
        """Should list all keys."""
        await storage.set("key1", "value1")
        await storage.set("key2", "value2")
        
        result = await storage.list_keys()
        
        assert len(result) == 2
        assert "key1" in result
        assert "key2" in result

    @pytest.mark.asyncio
    async def test_list_keys_with_namespace(self, storage):
        """Should list keys in specific namespace."""
        await storage.set("key1", "value1", namespace="ns1")
        await storage.set("key2", "value2", namespace="ns2")
        
        result_ns1 = await storage.list_keys(namespace="ns1")
        
        assert result_ns1 == ["key1"]

    @pytest.mark.asyncio
    async def test_list_keys_with_pattern(self, storage):
        """Should list keys matching pattern."""
        await storage.set("user1", "value1")
        await storage.set("user2", "value2")
        await storage.set("post1", "value3")
        
        result = await storage.list_keys(pattern="user*")
        
        assert len(result) == 2
        assert "user1" in result
        assert "user2" in result
        assert "post1" not in result

    @pytest.mark.asyncio
    async def test_clear_namespace(self, storage):
        """Should clear specific namespace."""
        await storage.set("key1", "value1", namespace="ns1")
        await storage.set("key2", "value2", namespace="ns2")
        
        await storage.clear(namespace="ns1")
        
        assert await storage.get("key1", namespace="ns1") is None
        assert await storage.get("key2", namespace="ns2") == "value2"

    @pytest.mark.asyncio
    async def test_get_stats(self, storage):
        """Should return storage statistics."""
        await storage.set("key1", "value1", namespace="ns1")
        await storage.set("key2", "value2", namespace="ns1")
        
        stats = storage.get_stats()
        
        assert stats["total_entries"] == 2
        assert "ns1" in stats["namespaces"]
        assert stats["namespaces"]["ns1"]["entries"] == 2


class TestInMemoryStorageWithDefaults:
    """Tests for InMemoryStorage with default settings."""

    @pytest.fixture(autouse=True)
    def setup_clock(self):
        fixed = FixedClock()
        with ambient_clock.use(fixed):
            yield

    @pytest.mark.asyncio
    async def test_default_ttl(self):
        """Should use default TTL when not specified."""
        storage = InMemoryStorage(default_ttl=30)
        await storage.set("key1", "value1")

        result = await storage.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_no_default_ttl(self):
        """Should work without default TTL."""
        storage = InMemoryStorage()
        await storage.set("key1", "value1")

        result = await storage.get("key1")
        assert result == "value1"
