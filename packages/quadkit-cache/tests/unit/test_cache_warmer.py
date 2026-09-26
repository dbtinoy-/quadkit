"""Tests for cache warmer service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.cache.service.warmer import CacheWarmer


class TestCacheWarmer:
    def test_warmer_initialization(self) -> None:
        mock_cache = MagicMock()
        warmer = CacheWarmer(cache=mock_cache, concurrency=5)
        assert warmer._cache is mock_cache
        assert warmer._concurrency == 5

    def test_warmer_default_concurrency(self) -> None:
        mock_cache = MagicMock()
        warmer = CacheWarmer(cache=mock_cache)
        assert warmer._concurrency == 10

    @pytest.mark.asyncio
    async def test_warm_empty_keys(self) -> None:
        mock_cache = MagicMock()
        warmer = CacheWarmer(cache=mock_cache)
        
        async def loader(key: str) -> str:
            return f"value_{key}"
        
        result = await warmer.warm(keys=[], loader=loader)
        assert result == {}

    @pytest.mark.asyncio
    async def test_warm_with_loader(self) -> None:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        
        warmer = CacheWarmer(cache=mock_cache)
        
        async def loader(key: str) -> str:
            return f"value_{key}"
        
        result = await warmer.warm(keys=["key1", "key2"], loader=loader)
        assert "key1" in result
        assert "key2" in result

    @pytest.mark.asyncio
    async def test_warm_skip_existing(self) -> None:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value="existing_value")
        mock_cache.set = AsyncMock(return_value=True)
        
        warmer = CacheWarmer(cache=mock_cache)
        
        async def loader(key: str) -> str:
            return f"value_{key}"
        
        result = await warmer.warm(keys=["key1"], loader=loader, skip_existing=True)
        assert result["key1"] is True

    @pytest.mark.asyncio
    async def test_warm_no_skip_existing(self) -> None:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value="existing_value")
        mock_cache.set = AsyncMock(return_value=True)
        
        warmer = CacheWarmer(cache=mock_cache)
        
        async def loader(key: str) -> str:
            return f"value_{key}"
        
        result = await warmer.warm(keys=["key1"], loader=loader, skip_existing=False)
        assert result["key1"] is True
        mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_warm_with_ttl(self) -> None:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        
        warmer = CacheWarmer(cache=mock_cache)
        
        async def loader(key: str) -> str:
            return f"value_{key}"
        
        await warmer.warm(keys=["key1"], loader=loader, ttl=300)
        mock_cache.set.assert_called_with("key1", "value_key1", ttl=300)

    @pytest.mark.asyncio
    async def test_warm_dict_empty(self) -> None:
        mock_cache = MagicMock()
        warmer = CacheWarmer(cache=mock_cache)
        
        result = await warmer.warm_dict(data={})
        assert result == 0

    @pytest.mark.asyncio
    async def test_warm_dict(self) -> None:
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=True)
        
        warmer = CacheWarmer(cache=mock_cache)
        
        data = {"key1": "value1", "key2": "value2"}
        result = await warmer.warm_dict(data=data)
        assert result == 2

    @pytest.mark.asyncio
    async def test_warm_dict_with_ttl(self) -> None:
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=True)
        
        warmer = CacheWarmer(cache=mock_cache)
        
        data = {"key1": "value1"}
        result = await warmer.warm_dict(data=data, ttl=600)
        assert result == 1
        mock_cache.set.assert_called_with("key1", "value1", ttl=600)
