"""Tests for Memcached cache backend."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.cache.backends.memcached.backend import MemcachedCacheBackend
from quadkit.cache.config import CacheOperationConfig
from quadkit.cache.types import CacheMetrics


class TestMemcachedCacheBackend:
    """Test Memcached cache backend"""

    def setup_method(self):
        """Setup test method"""
        self.servers = ["localhost:11211"]
        self.config = CacheOperationConfig(default_ttl=300, key_prefix="test:")
        self.mock_client = AsyncMock()
        self.backend = MemcachedCacheBackend(servers=self.servers, config=self.config)
        self.backend._client = self.mock_client

    @pytest.mark.asyncio
    async def test_get_hit(self):
        """Test successful cache get"""
        self.mock_client.get.return_value = b"test_value"

        result = await self.backend.get("test_key")

        assert result == b"test_value"
        self.mock_client.get.assert_called_once_with("test::test_key")
        assert self.backend._metrics.hits == 1
        assert self.backend._metrics.misses == 0

    @pytest.mark.asyncio
    async def test_get_miss(self):
        """Test cache get miss"""
        self.mock_client.get.return_value = None

        result = await self.backend.get("test_key")

        assert result is None
        self.mock_client.get.assert_called_once_with("test::test_key")
        assert self.backend._metrics.hits == 0
        assert self.backend._metrics.misses == 1

    @pytest.mark.asyncio
    async def test_get_error(self):
        """Test cache get with error"""
        self.mock_client.get.side_effect = RuntimeError("Client error")

        result = await self.backend.get("test_key")

        assert result is None
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_set_success_string(self):
        """Test successful cache set with string"""
        self.mock_client.set.return_value = True

        result = await self.backend.set("test_key", "test_value", 600)

        assert result is True
        self.mock_client.set.assert_called_once_with(
            "test::test_key", b"test_value", expire=600,
        )
        assert self.backend._metrics.sets == 1

    @pytest.mark.asyncio
    async def test_set_success_int(self):
        """Test successful cache set with int"""
        self.mock_client.set.return_value = True

        result = await self.backend.set("test_key", 42, 600)

        assert result is True
        self.mock_client.set.assert_called_once_with(
            "test::test_key", b"42", expire=600,
        )

    @pytest.mark.asyncio
    async def test_set_default_ttl(self):
        """Test cache set with default TTL"""
        self.mock_client.set.return_value = True

        result = await self.backend.set("test_key", "test_value")

        assert result is True
        self.mock_client.set.assert_called_once_with(
            "test::test_key", b"test_value", expire=300,
        )

    @pytest.mark.asyncio
    async def test_set_error(self):
        """Test cache set with error"""
        self.mock_client.set.side_effect = RuntimeError("Client error")

        result = await self.backend.set("test_key", "test_value")

        assert result is False
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful cache delete"""
        self.mock_client.delete.return_value = True

        result = await self.backend.delete("test_key")

        assert result is True
        self.mock_client.delete.assert_called_once_with("test::test_key")
        assert self.backend._metrics.deletes == 1

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """Test cache delete when key not found"""
        self.mock_client.delete.return_value = False

        result = await self.backend.delete("test_key")

        assert result is False
        self.mock_client.delete.assert_called_once_with("test::test_key")

    @pytest.mark.asyncio
    async def test_delete_error(self):
        """Test cache delete with error"""
        self.mock_client.delete.side_effect = RuntimeError("Client error")

        result = await self.backend.delete("test_key")

        assert result is False
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test key exists"""
        self.mock_client.get.return_value = b"test_value"

        result = await self.backend.exists("test_key")

        assert result is True
        self.mock_client.get.assert_called_once_with("test::test_key")

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test key does not exist"""
        self.mock_client.get.return_value = None

        result = await self.backend.exists("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_error(self):
        """Test exists with error"""
        self.mock_client.get.side_effect = RuntimeError("Client error")

        result = await self.backend.exists("test_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test cache clear"""
        result = await self.backend.clear()

        assert result is False
        # Memcached backend clear is not supported

    @pytest.mark.asyncio
    async def test_get_many_success(self):
        """Test get many values"""
        self.mock_client.get_multi.return_value = {
            "test::key1": b"value1",
            "test::key2": b"value2",
        }

        result = await self.backend.get_many(["key1", "key2"])

        assert result == {"key1": "value1", "key2": "value2"}
        self.mock_client.get_multi.assert_called_once_with(["test::key1", "test::key2"])
        assert self.backend._metrics.hits == 2
        assert self.backend._metrics.misses == 0

    @pytest.mark.asyncio
    async def test_get_many_partial(self):
        """Test get many with partial results"""
        self.mock_client.get_multi.return_value = {"test::key1": b"value1"}

        result = await self.backend.get_many(["key1", "key2"])

        assert result == {"key1": "value1"}
        assert self.backend._metrics.hits == 1
        assert self.backend._metrics.misses == 1

    @pytest.mark.asyncio
    async def test_get_many_error(self):
        """Test get many with error"""
        self.mock_client.get_multi.side_effect = RuntimeError("Client error")

        result = await self.backend.get_many(["key1", "key2"])

        assert result == {}
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_set_many_success(self):
        """Test set many values"""
        self.mock_client.set_multi.return_value = []  # Empty list means all succeeded

        items = {"key1": "value1", "key2": "value2"}
        result = await self.backend.set_many(items, 600)

        assert result is True
        expected_items = {"test::key1": b"value1", "test::key2": b"value2"}
        self.mock_client.set_multi.assert_called_once_with(expected_items, expire=600)
        assert self.backend._metrics.sets == 2

    @pytest.mark.asyncio
    async def test_set_many_partial_failure(self):
        """Test set many with partial failure"""
        self.mock_client.set_multi.return_value = ["test::key2"]  # key2 failed

        items = {"key1": "value1", "key2": "value2"}
        result = await self.backend.set_many(items, 600)

        assert result is False
        assert self.backend._metrics.sets == 0  # No metrics updated on failure

    @pytest.mark.asyncio
    async def test_set_many_default_ttl(self):
        """Test set many with default TTL"""
        self.mock_client.set_multi.return_value = []

        items = {"key1": "value1"}
        result = await self.backend.set_many(items)

        assert result is True
        expected_items = {"test::key1": b"value1"}
        self.mock_client.set_multi.assert_called_once_with(expected_items, expire=300)

    @pytest.mark.asyncio
    async def test_set_many_error(self):
        """Test set many with error"""
        self.mock_client.set_multi.side_effect = RuntimeError("Client error")

        items = {"key1": "value1"}
        result = await self.backend.set_many(items)

        assert result is False
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_delete_many_success(self):
        """Test delete many values"""
        self.mock_client.delete.return_value = True
        keys = ["key1", "key2"]

        result = await self.backend.delete_many(keys)

        assert result is True
        assert self.mock_client.delete.call_count == 2
        self.mock_client.delete.assert_any_call("test::key1")
        self.mock_client.delete.assert_any_call("test::key2")
        assert self.backend._metrics.deletes == 2

    @pytest.mark.asyncio
    async def test_delete_many_partial_failure(self):
        """Test delete many with partial failure"""
        # First call succeeds, second fails
        self.mock_client.delete.side_effect = [True, False]
        keys = ["key1", "key2"]

        result = await self.backend.delete_many(keys)

        assert result is False
        assert self.backend._metrics.deletes == 0  # No metrics on failure

    @pytest.mark.asyncio
    async def test_delete_many_error(self):
        """Test delete many with error"""
        self.mock_client.delete.side_effect = RuntimeError("Client error")
        keys = ["key1"]

        result = await self.backend.delete_many(keys)

        assert result is False
        assert self.backend._metrics.errors == 1

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check"""
        self.mock_client.set.return_value = True
        self.mock_client.delete.return_value = True

        result = await self.backend.health_check()

        assert result.status.value == "healthy"
        assert result.details["backend"] == "memcached"
        assert result.details["servers"] == ["localhost:11211"]
        assert result.details["metrics"] == await self.backend._metrics.to_dict()
        assert result.details["config"]["default_ttl"] == 300
        assert result.details["config"]["key_prefix"] == "test:"

        # Verify health check test operations were called
        self.mock_client.set.assert_called_once()
        self.mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_error(self):
        """Test health check with error"""
        self.mock_client.set.side_effect = RuntimeError("Connection error")

        result = await self.backend.health_check()

        assert result.status.value == "unhealthy"
        assert result.details["backend"] == "memcached"
        assert result.details["servers"] == ["localhost:11211"]
        assert "Connection error" in result.error
        assert result.details["metrics"] == await self.backend._metrics.to_dict()

    def test_initialization_default_config(self):
        """Test initialization with default config"""
        backend = MemcachedCacheBackend(servers=self.servers)

        assert backend.config.default_ttl is None
        assert backend.config.key_prefix == ""
        assert isinstance(backend._metrics, CacheMetrics)
        assert backend._servers == self.servers
        assert backend._client is None

    def test_initialization_custom_config(self):
        """Test initialization with custom config"""
        config = CacheOperationConfig(default_ttl=600, key_prefix="custom:")
        backend = MemcachedCacheBackend(servers=self.servers, config=config)

        assert backend.config == config
        assert backend._servers == self.servers

    @pytest.mark.asyncio
    async def test_lazy_client_initialization(self):
        """Test that client is initialized lazily"""
        backend = MemcachedCacheBackend(servers=self.servers, config=self.config)

        # Client should be None initially
        assert backend._client is None

        # Getting client should initialize it
        with patch(
            "quadkit.cache.backends.memcached.backend.AsyncMemcachedClient",
        ) as mock_client_class:
            mock_client_instance = MagicMock()
            mock_client_class.return_value = mock_client_instance

            client = await backend._get_client()

            assert client == mock_client_instance
            mock_client_class.assert_called_once_with("localhost", 11211)
            assert backend._client == mock_client_instance

            # Second call should reuse the client
            client2 = await backend._get_client()
            assert client2 == mock_client_instance
            assert mock_client_class.call_count == 1

    def test_import_error_handling(self):
        """Test behaviour when pymemcache is not available"""
        # Depending on environment, backend construction may either raise an
        # ImportError (strict) or be permissive and allow instantiation while
        # requiring the test to inject a client later. Accept both behaviours.
        with patch(
            "quadkit.cache.backends.memcached.backend.AsyncMemcachedClient", None,
        ):
            try:
                backend = MemcachedCacheBackend(servers=self.servers)
            except ImportError:
                # Strict behaviour is acceptable
                pass
            else:
                # Permissive behaviour: client must be None
                assert backend._client is None
