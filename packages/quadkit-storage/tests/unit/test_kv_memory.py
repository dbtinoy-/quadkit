"""Unit tests for InMemoryKVStorage."""

import pytest
import time

from quadkit.storage.kv.memory import InMemoryKVStorage
from quadkit.contracts.core import HealthStatus
from quadkit.contracts.infra.storage import StorageType


class TestInMemoryKVStorage:
    """Tests for InMemoryKVStorage class."""

    @pytest.fixture
    def storage(self):
        return InMemoryKVStorage()

    @pytest.mark.asyncio
    async def test_storage_type(self, storage):
        assert storage.storage_type == StorageType.MEMORY

    @pytest.mark.asyncio
    async def test_connect(self, storage):
        await storage.connect()
        assert storage._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, storage):
        await storage.connect()
        await storage.disconnect()
        assert storage._connected is False

    @pytest.mark.asyncio
    async def test_set_and_get(self, storage):
        await storage.set("key1", "value1")
        result = await storage.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, storage):
        result = await storage.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_namespace(self, storage):
        await storage.set("key1", "value1", namespace="ns1")
        result = await storage.get("key1", namespace="ns1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_with_different_namespace(self, storage):
        await storage.set("key1", "value1", namespace="ns1")
        result = await storage.get("key1", namespace="ns2")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing_key(self, storage):
        await storage.set("key1", "value1")
        result = await storage.delete("key1")
        assert result is True
        assert await storage.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self, storage):
        result = await storage.delete("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, storage):
        await storage.set("key1", "value1")
        result = await storage.exists("key1")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, storage):
        result = await storage.exists("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_keys_empty(self, storage):
        result = await storage.list_keys()
        assert result == []

    @pytest.mark.asyncio
    async def test_list_keys_single(self, storage):
        await storage.set("key1", "value1")
        result = await storage.list_keys()
        assert result == ["key1"]

    @pytest.mark.asyncio
    async def test_list_keys_with_namespace(self, storage):
        await storage.set("key1", "value1", namespace="ns1")
        await storage.set("key2", "value2", namespace="ns2")
        
        result_ns1 = await storage.list_keys(namespace="ns1")
        result_ns2 = await storage.list_keys(namespace="ns2")
        
        assert result_ns1 == ["key1"]
        assert result_ns2 == ["key2"]

    @pytest.mark.asyncio
    async def test_list_keys_pattern(self, storage):
        await storage.set("user:1", "value1")
        await storage.set("user:2", "value2")
        await storage.set("post:1", "value3")
        
        result = await storage.list_keys(pattern="user:*")
        assert result == ["user:1", "user:2"]

    @pytest.mark.asyncio
    async def test_clear_all(self, storage):
        await storage.set("key1", "value1")
        await storage.set("key2", "value2")
        
        result = await storage.clear()
        assert result is True
        assert await storage.list_keys() == []

    @pytest.mark.asyncio
    async def test_clear_namespace(self, storage):
        await storage.set("key1", "value1", namespace="ns1")
        await storage.set("key2", "value2", namespace="ns2")
        
        result = await storage.clear(namespace="ns1")
        assert result is True
        
        assert await storage.get("key1", namespace="ns1") is None
        assert await storage.get("key2", namespace="ns2") == "value2"

    @pytest.mark.asyncio
    async def test_ttl_expired(self, storage):
        await storage.set("key1", "value1", ttl=1)  # 1 second TTL
        # Wait briefly to ensure TTL expires
        time.sleep(1.1)
        result = await storage.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self, storage):
        await storage.set("key1", "value1", ttl=60)
        result = await storage.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_ttl_none(self, storage):
        await storage.set("key1", "value1", ttl=None)
        result = await storage.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_ttl_negative_ignored(self, storage):
        await storage.set("key1", "value1", ttl=-1)
        result = await storage.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, storage):
        result = await storage.health_check()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "in_memory_kv"
        assert "entry_count" in result.details

    @pytest.mark.asyncio
    async def test_full_key_with_namespace(self, storage):
        full = storage._full_key("key1", "ns1")
        assert full == "ns1:key1"

    @pytest.mark.asyncio
    async def test_full_key_without_namespace(self, storage):
        full = storage._full_key("key1", None)
        assert full == "key1"

    @pytest.mark.asyncio
    async def test_is_alive_none(self, storage):
        assert storage._is_alive(None) is True

    @pytest.mark.asyncio
    async def test_is_alive_future(self, storage):
        future_ns = time.monotonic_ns() + 1_000_000_000  # 1 second from now
        assert storage._is_alive(future_ns) is True

    @pytest.mark.asyncio
    async def test_is_alive_past(self, storage):
        past_ns = time.monotonic_ns() - 1_000_000_000  # 1 second ago
        assert storage._is_alive(past_ns) is False

    @pytest.mark.asyncio
    async def test_list_keys_removes_expired(self, storage):
        await storage.set("key1", "value1", ttl=1)
        time.sleep(1.1)
        
        result = await storage.list_keys()
        assert result == []

    @pytest.mark.asyncio
    async def test_set_returns_true(self, storage):
        result = await storage.set("key1", "value1")
        assert result is True
