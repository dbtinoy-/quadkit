"""Repository hook initialization and RepositoryError tests."""

#!/usr/bin/env python3
"""Unit tests for RepositoryProtocol"""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.sql.exceptions import DatabaseError, RepositoryError
from quadkit.sql.repositories.base import SQLRepository




class TestRepositoryHookInitialization:
    """SQLRepository must properly initialize post-save/post-delete hooks."""

    @pytest.fixture
    def mock_provider(self):
        provider = Mock()
        provider.execute_query = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        return provider

    @pytest.fixture
    def concrete_repository(self, mock_provider):
        class TestEntity:
            def __init__(self, id=None, name=""):
                self.id = id
                self.name = name

        class ConcreteRepository(SQLRepository[TestEntity, int]):
            def _entity_to_dict(self, entity):
                return {"id": entity.id, "name": entity.name}
            def _row_to_entity(self, row):
                return TestEntity(id=row.get("id"), name=row.get("name", ""))

        return ConcreteRepository(mock_provider, "test_entities", "id")

    def test_hook_lists_initialized(self, concrete_repository):
        """_post_save_hooks and _post_delete_hooks must be empty lists."""
        assert concrete_repository._post_save_hooks == []
        assert concrete_repository._post_delete_hooks == []

    def test_register_post_save_hook_appends(self, concrete_repository):
        """register_post_save_hook adds callback."""
        callback = Mock()
        concrete_repository.register_post_save_hook(callback)
        assert callback in concrete_repository._post_save_hooks

    def test_register_post_delete_hook_appends(self, concrete_repository):
        """register_post_delete_hook adds callback."""
        callback = Mock()
        concrete_repository.register_post_delete_hook(callback)
        assert callback in concrete_repository._post_delete_hooks

    @pytest.mark.asyncio
    async def test_delete_fires_post_delete_hooks(self, concrete_repository, mock_provider):
        """SQLRepository.delete() must fire registered post-delete hooks."""
        hook = AsyncMock()
        concrete_repository.register_post_delete_hook(hook)
        entity = concrete_repository._row_to_entity({"id": 42, "name": "del"})
        delete_result = Mock()
        delete_result.success = True
        mock_provider.execute_delete.return_value = delete_result

        await concrete_repository.delete(entity)

        hook.assert_awaited_once_with(42)


class TestRepositoryError:
    """Test RepositoryError exception"""

    def test_repository_error_creation(self):
        """Test creating a RepositoryError"""
        error = RepositoryError("test error")
        assert "[QK_ERR_SQL_023]" in str(error)
        assert "test error" in str(error)


