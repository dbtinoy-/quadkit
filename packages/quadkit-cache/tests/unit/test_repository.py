"""
Unit tests for repository patterns.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.cache.repository import (
    CacheRepository,
    CollectionRepository,
    ConfigurationRepository,
    EntityRepository,
    QueryRepository,
)


class TestCacheRepository:
    """Test base cache repository functionality."""

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        service = MagicMock()
        service.get = AsyncMock(return_value=None)
        service.set = AsyncMock(return_value=True)
        service.delete = AsyncMock(return_value=True)
        service.exists = AsyncMock(return_value=False)
        service.get_or_set = AsyncMock(return_value="test_value")
        return service

    @pytest.fixture
    def repository(self, mock_cache_service):
        """Create test repository."""
        return CacheRepository[str, str](mock_cache_service, "test", 300)

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_cached(
        self, repository, mock_cache_service,
    ):
        """Test get returns None when item not in cache."""
        mock_cache_service.get.return_value = None

        result = await repository.get("test_key")

        assert result is None
        mock_cache_service.get.assert_called_once_with("test:test_key")

    @pytest.mark.asyncio
    async def test_set_calls_cache_service(self, repository, mock_cache_service):
        """Test set calls cache service with correct key."""
        result = await repository.set("test_key", "test_value")

        assert result is True
        mock_cache_service.set.assert_called_once_with(
            "test:test_key", "test_value", 300,
        )

    @pytest.mark.asyncio
    async def test_delete_calls_cache_service(self, repository, mock_cache_service):
        """Test delete calls cache service."""
        result = await repository.delete("test_key")

        assert result is True
        mock_cache_service.delete.assert_called_once_with("test:test_key")


class TestEntityRepository:
    """Test entity repository functionality."""

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        service = MagicMock()
        service.get = AsyncMock(return_value={"id": "123", "name": "Test"})
        service.set = AsyncMock(return_value=True)
        service.get_many = AsyncMock(
            return_value={"entity:user:123": {"id": "123", "name": "Test"}},
        )
        return service

    @pytest.fixture
    def user_repository(self, mock_cache_service):
        """Create user entity repository."""
        return EntityRepository[dict[str, str], str](mock_cache_service, "user", 3600)

    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repository, mock_cache_service):
        """Test getting entity by ID."""
        result = await user_repository.get_by_id("123")

        assert result == {"id": "123", "name": "Test"}
        mock_cache_service.get.assert_called_once_with("entity:user:123")

    @pytest.mark.asyncio
    async def test_save_entity(self, user_repository, mock_cache_service):
        """Test saving entity."""
        entity = {"id": "123", "name": "Test User"}

        result = await user_repository.save(entity)

        assert result is True
        mock_cache_service.set.assert_called_once_with("entity:user:123", entity, 3600)

    @pytest.mark.asyncio
    async def test_get_multiple_entities(self, user_repository, mock_cache_service):
        """Test getting multiple entities."""
        result = await user_repository.get_multiple(["123", "456"])

        expected = {"123": {"id": "123", "name": "Test"}}
        assert result == expected

    def test_observe_registers_repository_hooks_only_once(
        self, user_repository,
    ) -> None:
        """Test observe only wires post-save and post-delete hooks once per repo."""
        source_repository = MagicMock()

        user_repository.observe(source_repository)
        user_repository.observe(source_repository)

        source_repository.register_post_save_hook.assert_called_once_with(
            user_repository.invalidate_by_entity,
        )
        source_repository.register_post_delete_hook.assert_called_once_with(
            user_repository.invalidate,
        )


class TestQueryRepository:
    """Test query repository functionality."""

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        service = MagicMock()
        service.get_or_set = AsyncMock(return_value=[{"id": "1", "name": "Product"}])
        return service

    @pytest.fixture
    def query_repository(self, mock_cache_service):
        """Create query repository."""
        return QueryRepository[list[dict[str, str]]](mock_cache_service, "search", 1800)

    @pytest.mark.asyncio
    async def test_get_query_result(self, query_repository, mock_cache_service):
        """Test getting query result."""
        query_params = {"q": "test", "limit": 10}

        async def mock_func():
            return [{"id": "1", "name": "Product"}]

        result = await query_repository.get_query_result(query_params, mock_func)

        assert result == [{"id": "1", "name": "Product"}]
        mock_cache_service.get_or_set.assert_called_once()


class TestCollectionRepository:
    """Test collection repository functionality."""

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        service = MagicMock()
        service.get_or_set = AsyncMock(return_value=[{"id": "1", "name": "Item"}])
        return service

    @pytest.fixture
    def collection_repository(self, mock_cache_service):
        """Create collection repository."""
        return CollectionRepository[dict[str, str]](mock_cache_service, "items", 900)

    @pytest.mark.asyncio
    async def test_get_collection_with_default_func(
        self, collection_repository, mock_cache_service,
    ):
        """Test getting collection with default function."""

        async def fetch_items():
            return [{"id": "1", "name": "Item"}]

        result = await collection_repository.get_collection(
            filters={"active": True}, default_func=fetch_items,
        )

        assert result == [{"id": "1", "name": "Item"}]


class TestConfigurationRepository:
    """Test configuration repository functionality."""

    @pytest.fixture
    def mock_cache_service(self):
        """Mock cache service."""
        service = MagicMock()
        service.get_or_set = AsyncMock(return_value={"setting": "value"})
        service.get = AsyncMock(return_value={"setting": "value"})
        return service

    @pytest.fixture
    def config_repository(self, mock_cache_service):
        """Create configuration repository."""
        return ConfigurationRepository(mock_cache_service, "app", 3600)

    @pytest.mark.asyncio
    async def test_get_config(self, config_repository, mock_cache_service):
        """Test getting configuration."""

        async def load_config():
            return {"setting": "value"}

        result = await config_repository.get_config(
            "database", default_func=load_config,
        )

        assert result == {"setting": "value"}

    @pytest.mark.asyncio
    async def test_get_config_value(self, config_repository, mock_cache_service):
        """Test getting specific config value."""
        result = await config_repository.get_config_value(
            "database", "host", default="localhost",
        )

        assert result == "localhost"
