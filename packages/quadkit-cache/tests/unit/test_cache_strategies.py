"""Unit tests for cache strategies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.cache import CacheService
from quadkit.cache.strategies.tiered import TieredCache
from quadkit.cache.strategies.write_through import WriteThroughCache


class TestTieredCacheStrategy:
    """Test suite for TieredCache strategy."""

    @pytest.fixture
    def mock_cache_service(self):
        """Create a mock cache service."""
        service = MagicMock(spec=CacheService)
        service.get = AsyncMock()
        service.set = AsyncMock(return_value=True)
        service.delete = AsyncMock(return_value=True)
        service.get_backend = MagicMock()
        return service

    @pytest.fixture
    def tiered_cache(self, mock_cache_service):
        """Create a TieredCache instance."""
        return TieredCache(
            cache_service=mock_cache_service,
            l1_backend="memory",
            l2_backend="redis",
            l1_ttl_multiplier=0.5,
        )

    @pytest.mark.asyncio
    async def test_get_l1_hit(self, tiered_cache, mock_cache_service):
        """Test get returns L1 value on L1 hit."""
        mock_cache_service.get.return_value = "l1_value"

        result = await tiered_cache.get("key1")

        assert result == "l1_value"
        mock_cache_service.get.assert_called_once_with("key1", backend="memory")
        mock_cache_service.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_l2_hit_backfills_l1(self, tiered_cache, mock_cache_service):
        """Test get returns L2 value and backfills L1."""
        mock_cache_service.get.side_effect = [None, "l2_value"]

        result = await tiered_cache.get("key1")

        assert result == "l2_value"
        assert mock_cache_service.get.call_count == 2
        mock_cache_service.get.assert_any_call("key1", backend="memory")
        mock_cache_service.get.assert_any_call("key1", backend="redis")
        mock_cache_service.set.assert_called_once_with(
            "key1", "l2_value", backend="memory"
        )

    @pytest.mark.asyncio
    async def test_get_miss_returns_default(self, tiered_cache, mock_cache_service):
        """Test get returns default when both tiers miss."""
        mock_cache_service.get.return_value = None

        result = await tiered_cache.get("nonexistent", default="default")

        assert result == "default"

    @pytest.mark.asyncio
    async def test_set_writes_to_both_tiers(self, tiered_cache, mock_cache_service):
        """Test set writes to both L1 and L2 with appropriate TTLs."""
        mock_cache_service.set.return_value = True

        result = await tiered_cache.set("key1", "value", ttl=100)

        assert result is True
        assert mock_cache_service.set.call_count == 2
        mock_cache_service.set.assert_any_call("key1", "value", ttl=50, backend="memory")
        mock_cache_service.set.assert_any_call("key1", "value", ttl=100, backend="redis")

    @pytest.mark.asyncio
    async def test_set_without_ttl(self, tiered_cache, mock_cache_service):
        """Test set with no TTL uses None for both tiers."""
        mock_cache_service.set.return_value = True

        await tiered_cache.set("key1", "value")

        mock_cache_service.set.assert_any_call("key1", "value", ttl=None, backend="memory")
        mock_cache_service.set.assert_any_call("key1", "value", ttl=None, backend="redis")

    @pytest.mark.asyncio
    async def test_delete_removes_from_both_tiers(self, tiered_cache, mock_cache_service):
        """Test delete removes from both tiers."""
        mock_cache_service.delete.return_value = True

        result = await tiered_cache.delete("key1")

        assert result is True
        mock_cache_service.delete.assert_any_call("key1", backend="memory")
        mock_cache_service.delete.assert_any_call("key1", backend="redis")

    @pytest.mark.asyncio
    async def test_get_or_set_cache_hit(self, tiered_cache, mock_cache_service):
        """Test get_or_set returns cached value on hit."""
        mock_cache_service.get.return_value = "cached"

        result = await tiered_cache.get_or_set("key1", lambda: "computed")

        assert result == "cached"
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_set_cache_miss_computes_and_caches(
        self, tiered_cache, mock_cache_service
    ):
        """Test get_or_set computes and caches on miss."""
        mock_cache_service.get.return_value = None

        result = await tiered_cache.get_or_set("key1", lambda: "computed", ttl=60)

        assert result == "computed"
        mock_cache_service.set.assert_called()

    @pytest.mark.asyncio
    async def test_get_or_set_with_async_default(self, tiered_cache, mock_cache_service):
        """Test get_or_set handles async default functions."""
        mock_cache_service.get.return_value = None

        async def async_default():
            return "async_computed"

        result = await tiered_cache.get_or_set("key1", async_default)

        assert result == "async_computed"

    @pytest.mark.asyncio
    async def test_shutdown_closes_backends(self, tiered_cache, mock_cache_service):
        """Test shutdown closes both backend tiers."""
        mock_l1 = MagicMock()
        mock_l1.close = AsyncMock()
        mock_l2 = MagicMock()
        mock_l2.close = AsyncMock()
        mock_cache_service.get_backend.side_effect = [mock_l1, mock_l2]

        await tiered_cache.shutdown()

        mock_l1.close.assert_called_once()
        mock_l2.close.assert_called_once()


class TestWriteThroughStrategy:
    """Test suite for WriteThroughCache strategy."""

    @pytest.fixture
    def mock_cache_service(self):
        """Create a mock cache service."""
        service = MagicMock(spec=CacheService)
        service.get = AsyncMock()
        service.set = AsyncMock(return_value=True)
        service.delete = AsyncMock(return_value=True)
        return service

    @pytest.fixture
    def write_through_cache(self, mock_cache_service):
        """Create a WriteThroughCache instance."""
        return WriteThroughCache(
            cache_service=mock_cache_service,
            namespace="users",
            ttl=300,
            key_field="id",
        )

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, write_through_cache, mock_cache_service):
        """Test get returns cached value on hit."""
        mock_cache_service.get.return_value = {"id": "1", "name": "Test"}

        result = await write_through_cache.get("1", lambda: {"id": "1"})

        assert result == {"id": "1", "name": "Test"}
        mock_cache_service.get.assert_called_once_with("users:1")
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_cache_miss_loads_and_caches(
        self, write_through_cache, mock_cache_service
    ):
        """Test get loads from loader and caches on miss."""
        mock_cache_service.get.return_value = None

        async def loader():
            return {"id": "1", "name": "Test"}

        result = await write_through_cache.get("1", loader)

        assert result == {"id": "1", "name": "Test"}
        mock_cache_service.get.assert_called_once_with("users:1")
        mock_cache_service.set.assert_called_once_with(
            "users:1", {"id": "1", "name": "Test"}, 300
        )

    @pytest.mark.asyncio
    async def test_get_returns_none_when_loader_returns_none(
        self, write_through_cache, mock_cache_service
    ):
        """Test get returns None without caching when loader returns None."""
        mock_cache_service.get.return_value = None

        async def loader():
            return None

        result = await write_through_cache.get("1", loader)

        assert result is None
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_writes_to_primary_and_cache(
        self, write_through_cache, mock_cache_service
    ):
        """Test update writes to primary store and cache."""
        writer = AsyncMock(return_value={"id": "1", "name": "Updated"})

        result = await write_through_cache.update("1", {"id": "1", "name": "Updated"}, writer)

        writer.assert_called_once_with({"id": "1", "name": "Updated"})
        mock_cache_service.set.assert_called_once_with(
            "users:1", {"id": "1", "name": "Updated"}, 300
        )
        assert result == {"id": "1", "name": "Updated"}

    @pytest.mark.asyncio
    async def test_delete_removes_from_primary_and_cache(
        self, write_through_cache, mock_cache_service
    ):
        """Test delete removes from primary and cache."""
        deleter = AsyncMock(return_value=True)

        result = await write_through_cache.delete("1", deleter)

        deleter.assert_called_once()
        mock_cache_service.delete.assert_called_once_with("users:1")
        assert result is True

    @pytest.mark.asyncio
    async def test_shutdown_is_noop(self, write_through_cache):
        """Test shutdown is a no-op for write-through cache."""
        await write_through_cache.shutdown()

    @pytest.mark.asyncio
    async def test_make_key(self, write_through_cache):
        """Test key generation."""
        assert write_through_cache._make_key("123") == "users:123"
        assert write_through_cache._make_key("abc") == "users:abc"

    @pytest.mark.asyncio
    async def test_custom_namespace(self, mock_cache_service):
        """Test write-through with custom namespace."""
        cache = WriteThroughCache(
            cache_service=mock_cache_service,
            namespace="products",
            ttl=600,
        )
        assert cache._make_key("prod-001") == "products:prod-001"

    @pytest.mark.asyncio
    async def test_custom_ttl(self, mock_cache_service):
        """Test write-through with custom TTL."""
        cache = WriteThroughCache(
            cache_service=mock_cache_service,
            namespace="sessions",
            ttl=1800,
        )
        mock_cache_service.get.return_value = None

        async def loader():
            return {"session_id": "abc"}

        await cache.get("abc", loader)

        mock_cache_service.set.assert_called_once()
        call_kwargs = mock_cache_service.set.call_args
        assert call_kwargs[0][2] == 1800
