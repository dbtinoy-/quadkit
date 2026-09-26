"""Tests for memory cache backend."""

from unittest.mock import AsyncMock

import pytest

from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.config import CacheOperationConfig
from quadkit.cache.hooks import (
    CacheEntryEvictedHook,
    CacheHitHook,
    CacheMissHook,
)
from quadkit.cache.types import CacheMetrics
from quadkit.contracts.infra.cache.exceptions import CacheError
from quadkit.hooks import HookRegistry


class TestMemoryCacheBackend:
    """Test memory cache backend"""

    def setup_method(self):
        """Setup test method"""
        config = CacheOperationConfig(default_ttl=300, key_prefix="test")
        self.mock_store = AsyncMock()
        del self.mock_store.pipeline
        del self.mock_store.keys
        # Memory test needs clear() -> wait, test_clear calls it.
        # But we don't want pipeline or keys to return AsyncMocks.
        self.backend = MemoryCacheBackend(config)
        self.backend._store = self.mock_store

    @pytest.mark.asyncio
    async def test_get_hit(self):
        """Test successful cache get"""
        self.mock_store.get.return_value = "test_value"

        result = await self.backend.get("test_key")

        assert result.is_ok()
        assert result.unwrap() == "test_value"
        self.mock_store.get.assert_called_once_with("test:test_key")
        assert self.backend._metrics.hits == 1
        assert self.backend._metrics.misses == 0

    @pytest.mark.asyncio
    async def test_get_miss(self):
        """Test cache get miss"""
        self.mock_store.get.return_value = None

        result = await self.backend.get("test_key")

        assert result.is_ok()
        assert result.unwrap() is None
        self.mock_store.get.assert_called_once_with("test:test_key")
        assert self.backend._metrics.hits == 0
        assert self.backend._metrics.misses == 1

    @pytest.mark.asyncio
    async def test_get_error(self):
        """Test cache get with error"""
        self.mock_store.get.side_effect = ValueError("Store error")

        result = await self.backend.get("test_key")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), CacheError)
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_set_success(self):
        """Test successful cache set"""
        self.mock_store.set.return_value = None

        result = await self.backend.set("test_key", "test_value", 600)

        assert result.is_ok()
        assert result.unwrap() is None
        self.mock_store.set.assert_called_once_with("test:test_key", "test_value", 600)
        assert self.backend._metrics.sets == 1

    @pytest.mark.asyncio
    async def test_set_default_ttl(self):
        """Test cache set with default TTL"""
        self.mock_store.set.return_value = None

        result = await self.backend.set("test_key", "test_value")

        assert result.is_ok()
        assert result.unwrap() is None
        self.mock_store.set.assert_called_once_with("test:test_key", "test_value", 300)

    @pytest.mark.asyncio
    async def test_set_error(self):
        """Test cache set with error"""
        self.mock_store.set.side_effect = ValueError("Store error")

        result = await self.backend.set("test_key", "test_value")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), CacheError)
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful cache delete"""
        self.mock_store.delete.return_value = None

        result = await self.backend.delete("test_key")

        assert result.is_ok()
        assert result.unwrap() is True
        self.mock_store.delete.assert_called_once_with("test:test_key")
        assert self.backend._metrics.deletes == 1

    @pytest.mark.asyncio
    async def test_delete_error(self):
        """Test cache delete with error"""
        self.mock_store.delete.side_effect = ValueError("Store error")

        result = await self.backend.delete("test_key")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), CacheError)
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test key exists"""
        self.mock_store.get.return_value = "test_value"

        result = await self.backend.exists("test_key")

        assert result.is_ok()
        assert result.unwrap() is True
        self.mock_store.get.assert_called_once_with("test:test_key")

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test key does not exist"""
        self.mock_store.get.return_value = None

        result = await self.backend.exists("test_key")

        assert result.is_ok()
        assert result.unwrap() is False

    @pytest.mark.asyncio
    async def test_exists_error(self):
        """Test exists with error"""
        self.mock_store.get.side_effect = ValueError("Store error")

        result = await self.backend.exists("test_key")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), CacheError)

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test cache clear"""
        result = await self.backend.clear()

        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_get_many_success(self):
        """Test get many values"""
        self.mock_store.get_bulk.return_value = {
            "test:key1": "value1",
            "test:key2": "value2",
        }

        result = await self.backend.get_many(["key1", "key2"])

        assert result.is_ok()
        assert result.unwrap() == {"key1": "value1", "key2": "value2"}
        self.mock_store.get_bulk.assert_called_once_with(["test:key1", "test:key2"])
        assert self.backend._metrics.hits == 2
        assert self.backend._metrics.misses == 0

    @pytest.mark.asyncio
    async def test_get_many_partial(self):
        """Test get many with partial results"""
        self.mock_store.get_bulk.return_value = {"test:key1": "value1"}

        result = await self.backend.get_many(["key1", "key2"])

        assert result.is_ok()
        assert result.unwrap() == {"key1": "value1"}
        assert self.backend._metrics.hits == 1
        assert self.backend._metrics.misses == 1

    @pytest.mark.asyncio
    async def test_get_many_error(self):
        """Test get many with error"""
        self.mock_store.get_bulk.side_effect = ValueError("Store error")

        result = await self.backend.get_many(["key1", "key2"])

        assert result.is_err()
        assert isinstance(result.unwrap_err(), CacheError)
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_set_many_success(self):
        """Test set many values"""
        self.mock_store.set.return_value = None
        items = {"key1": "value1", "key2": "value2"}

        result = await self.backend.set_many(items, 600)

        assert result.is_ok()
        assert result.unwrap() is None
        self.mock_store.set.assert_any_call("test:key1", "value1", 600)
        self.mock_store.set.assert_any_call("test:key2", "value2", 600)
        assert self.backend._metrics.sets == 2

    @pytest.mark.asyncio
    async def test_set_many_default_ttl(self):
        """Test set many with default TTL"""
        self.mock_store.set.return_value = None
        items = {"key1": "value1"}

        result = await self.backend.set_many(items)

        assert result.is_ok()
        assert result.unwrap() is None
        self.mock_store.set.assert_called_once_with("test:key1", "value1", 300)

    @pytest.mark.asyncio
    async def test_set_many_error(self):
        """Test set many with error"""
        self.mock_store.set.side_effect = ValueError("Store error")
        items = {"key1": "value1"}

        result = await self.backend.set_many(items)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), CacheError)
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_delete_many_success(self):
        """Test delete many values"""
        self.mock_store.delete.return_value = None
        keys = ["key1", "key2"]

        result = await self.backend.delete_many(keys)

        assert result.is_ok()
        assert result.unwrap() == 2
        assert self.backend._metrics.deletes == 2

    @pytest.mark.asyncio
    async def test_delete_many_error(self):
        """Test delete many with error"""
        self.mock_store.delete.side_effect = ValueError("Store error")
        keys = ["key1"]

        result = await self.backend.delete_many(keys)

        assert result.is_err()
        assert isinstance(result.unwrap_err(), CacheError)
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check"""
        self.mock_store.health_check.return_value = {"status": "healthy"}

        result = await self.backend.health_check()

        assert result.status.value == "healthy"
        assert result.details["backend"] == "memory"
        assert result.details["store_health"] == {"status": "healthy"}
        assert result.details["metrics"] == await self.backend._metrics.to_dict()
        assert result.details["config"]["default_ttl"] == 300
        assert result.details["config"]["key_prefix"] == "test"

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        """Test health check with error"""
        self.mock_store.health_check.side_effect = RuntimeError("Store error")

        result = await self.backend.health_check()

        assert result.status.value == "unhealthy"
        assert result.details["backend"] == "memory"
        assert "Store error" in result.error
        assert result.details["metrics"] == await self.backend._metrics.to_dict()

    def test_initialization_default_config(self):
        """Test initialization with default config"""
        backend = MemoryCacheBackend()

        assert backend.config.default_ttl is None
        assert backend.config.key_prefix == ""
        assert isinstance(backend._metrics, CacheMetrics)

    def test_initialization_custom_config(self):
        """Test initialization with custom config"""
        config = CacheOperationConfig(default_ttl=600, key_prefix="custom:")
        backend = MemoryCacheBackend(config)

        assert backend.config == config


class TestMemoryCacheBackendHooks:
    """Tests for cache hook emission from the memory backend."""

    @pytest.mark.asyncio
    async def test_get_hit_emits_cache_hit_hook(self) -> None:
        """A cache hit emits ``cache.hit`` with the canonical payload."""
        received: list[CacheHitHook] = []
        registry = HookRegistry("cache-test")

        async def capture(payload: CacheHitHook) -> None:
            received.append(payload)

        registry.register_action("cache.hit", capture)

        backend = MemoryCacheBackend(
            CacheOperationConfig(default_ttl=300, key_prefix="test"),
            hooks=registry,
        )
        backend._store = AsyncMock()
        backend._store.get.return_value = "test_value"

        result = await backend.get("test_key")

        assert result.is_ok()
        assert received == [CacheHitHook(key="test_key", backend="memory")]

    @pytest.mark.asyncio
    async def test_get_miss_emits_cache_miss_hook(self) -> None:
        """A cache miss emits ``cache.miss`` with the canonical payload."""
        received: list[CacheMissHook] = []
        registry = HookRegistry("cache-test")

        async def capture(payload: CacheMissHook) -> None:
            received.append(payload)

        registry.register_action("cache.miss", capture)

        backend = MemoryCacheBackend(
            CacheOperationConfig(default_ttl=300, key_prefix="test"),
            hooks=registry,
        )
        backend._store = AsyncMock()
        backend._store.get.return_value = None

        result = await backend.get("missing_key")

        assert result.is_ok()
        assert received == [CacheMissHook(key="missing_key", backend="memory")]

    @pytest.mark.asyncio
    async def test_delete_emits_cache_evicted_hook(self) -> None:
        """Deleting an existing entry emits ``cache.evicted``."""
        received: list[CacheEntryEvictedHook] = []
        registry = HookRegistry("cache-test")

        async def capture(payload: CacheEntryEvictedHook) -> None:
            received.append(payload)

        registry.register_action("cache.evicted", capture)

        backend = MemoryCacheBackend(
            CacheOperationConfig(default_ttl=300, key_prefix="test"),
            hooks=registry,
        )
        backend._store = AsyncMock()
        backend._store.get.return_value = "test_value"
        backend._store.delete.return_value = True

        result = await backend.delete("test_key")

        assert result.is_ok()
        assert result.unwrap() is True
        assert received == [CacheEntryEvictedHook(key="test_key", backend="memory")]
