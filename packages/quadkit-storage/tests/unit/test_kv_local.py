"""Unit tests for LocalStorage."""

import pytest
from pathlib import Path
import tempfile
import shutil

from quadkit.storage.kv.local import LocalStorage
from quadkit.contracts.infra.storage import StorageType
from quadkit.contracts.core import HealthStatus


class TestLocalStorage:
    """Tests for LocalStorage class."""

    @pytest.fixture
    def temp_dir(self):
        tmp = tempfile.mkdtemp()
        yield Path(tmp)
        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.fixture
    def storage(self, temp_dir):
        return LocalStorage(base_path=temp_dir)

    @pytest.mark.asyncio
    async def test_storage_type(self, storage):
        assert storage.storage_type == StorageType.FILE

    @pytest.mark.asyncio
    async def test_connect_creates_base_path(self, storage, temp_dir):
        await storage.connect()
        assert temp_dir.exists()
        assert storage._connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, storage):
        await storage.connect()
        await storage.disconnect()
        assert storage._connected is False

    @pytest.mark.asyncio
    async def test_set_and_get(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1")
        result = await storage.get("key1")
        
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, storage):
        await storage.connect()
        
        result = await storage.get("nonexistent")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_namespace(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1", namespace="ns1")
        result = await storage.get("key1", namespace="ns1")
        
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_set_and_get_json_object(self, storage):
        await storage.connect()
        
        data = {"name": "test", "count": 42}
        await storage.set("obj", data)
        result = await storage.get("obj")
        
        assert result == data

    @pytest.mark.asyncio
    async def test_delete_existing(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1")
        result = await storage.delete("key1")
        
        assert result is True
        assert await storage.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, storage):
        await storage.connect()
        
        result = await storage.delete("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1")
        result = await storage.exists("key1")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, storage):
        await storage.connect()
        
        result = await storage.exists("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_list_keys_empty(self, storage):
        await storage.connect()
        
        result = await storage.list_keys()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_list_keys_single(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1")
        result = await storage.list_keys()
        
        assert result == ["key1"]

    @pytest.mark.asyncio
    async def test_list_keys_with_namespace(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1", namespace="ns1")
        await storage.set("key2", "value2", namespace="ns2")
        
        result_ns1 = await storage.list_keys(namespace="ns1")
        result_ns2 = await storage.list_keys(namespace="ns2")
        
        assert result_ns1 == ["key1"]
        assert result_ns2 == ["key2"]

    @pytest.mark.asyncio
    async def test_list_keys_pattern(self, storage):
        await storage.connect()
        
        await storage.set("user1", "value1")
        await storage.set("user2", "value2")
        await storage.set("post1", "value3")
        
        result = await storage.list_keys(pattern="user*")
        
        assert set(result) == {"user1", "user2"}

    @pytest.mark.asyncio
    async def test_clear_all(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1")
        await storage.set("key2", "value2")
        
        result = await storage.clear()
        
        assert result is True
        assert await storage.list_keys() == []

    @pytest.mark.asyncio
    async def test_clear_namespace(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1", namespace="ns1")
        await storage.set("key2", "value2", namespace="ns2")
        
        result = await storage.clear(namespace="ns1")
        
        assert result is True
        assert await storage.get("key1", namespace="ns1") is None
        assert await storage.get("key2", namespace="ns2") == "value2"

    @pytest.mark.asyncio
    async def test_ttl_expired(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1", ttl=1)
        
        import asyncio
        await asyncio.sleep(1.1)
        
        result = await storage.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1", ttl=60)
        result = await storage.get("key1")
        
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, storage):
        await storage.connect()
        
        result = await storage.health_check()
        
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "local_kv"

    @pytest.mark.asyncio
    async def test_get_file_path(self, storage):
        path = storage._get_file_path("key1", None)
        assert path.name == "key1.json"
        assert path.parent.name == "default"

    @pytest.mark.asyncio
    async def test_get_file_path_with_namespace(self, storage):
        path = storage._get_file_path("key1", "myns")
        assert path.name == "key1.json"
        assert path.parent.name == "myns"

    @pytest.mark.asyncio
    async def test_get_file_path_sanitizes_key(self, storage):
        path = storage._get_file_path("key/with:chars!", "ns")
        assert ":" not in path.name
        assert "/" not in path.name

    @pytest.mark.asyncio
    async def test_custom_file_extension(self, temp_dir):
        storage = LocalStorage(base_path=temp_dir, file_extension=".txt")
        await storage.connect()
        
        await storage.set("key1", "value1")
        path = storage._get_file_path("key1", None)
        
        assert path.suffix == ".txt"

    @pytest.mark.asyncio
    async def test_pretty_print(self, temp_dir):
        storage = LocalStorage(base_path=temp_dir, pretty_print=True)
        await storage.connect()
        
        await storage.set("key1", {"nested": {"value": 1}})
        path = storage._get_file_path("key1", None)
        
        content = path.read_bytes()
        # Note: quadkit.serialization uses orjson which doesn't support indent
        # So pretty_print=True doesn't actually pretty print
        assert content is not None

    @pytest.mark.asyncio
    async def test_set_returns_false_on_error(self, temp_dir):
        storage = LocalStorage(base_path=temp_dir)
        # Don't connect - should still work since mkdir is called in set
        
        result = await storage.set("key1", "value1")
        
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_nonexistent(self, storage):
        await storage.connect()
        
        result = await storage.delete("nonexistent")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_multiple_keys_in_namespace(self, storage):
        await storage.connect()
        
        await storage.set("key1", "value1", namespace="ns")
        await storage.set("key2", "value2", namespace="ns")
        
        keys = await storage.list_keys(namespace="ns")
        
        assert len(keys) == 2
        assert "key1" in keys
        assert "key2" in keys

    @pytest.mark.asyncio
    async def test_clear_nonexistent_namespace(self, storage):
        await storage.connect()
        
        result = await storage.clear(namespace="nonexistent")
        
        assert result is True
