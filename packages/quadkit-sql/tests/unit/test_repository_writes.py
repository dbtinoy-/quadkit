"""Repository write operations: create/update/delete."""

#!/usr/bin/env python3
"""Unit tests for RepositoryProtocol"""

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.sql.exceptions import DatabaseError, RepositoryError
from quadkit.sql.repositories.base import SQLRepository




class TestRepository:
    """Test RepositoryProtocol functionality"""

    @pytest.fixture
    def mock_provider(self):
        """Mock database provider"""
        provider = Mock()
        provider.execute_query = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        return provider

    @pytest.fixture
    def concrete_repository(self, mock_provider):
        """Create a concrete repository for testing"""

        class TestEntity:
            def __init__(self, id=None, name="", value=0):
                self.id = id
                self.name = name
                self.value = value

        class ConcreteRepository(SQLRepository[TestEntity, int]):
            def _entity_to_dict(self, entity: TestEntity) -> dict[str, Any]:
                return {"id": entity.id, "name": entity.name, "value": entity.value}

            def _row_to_entity(self, row: dict[str, Any]) -> TestEntity:
                return TestEntity(
                    id=row.get("id"),
                    name=row.get("name", ""),
                    value=row.get("value", 0),
                )

        return ConcreteRepository(mock_provider, "test_entities", "id")


    @pytest.mark.asyncio
    async def test_create_new_entity(self, concrete_repository, mock_provider):
        """Test creating a new entity"""
        # Create entity without ID
        entity = concrete_repository._row_to_entity({"name": "new", "value": 100})

        # Mock insert result
        insert_result = Mock()
        insert_result.success = True
        insert_result.inserted_id = 123
        mock_provider.execute_insert.return_value = insert_result

        result = await concrete_repository.create(entity)

        assert result.id == 123
        assert result.name == "new"
        assert result.value == 100

        # Timestamps are automatically added; assert essential fields and presence of timestamps
        called_args = mock_provider.execute_insert.call_args[0]
        assert called_args[0] == "test_entities"
        insert_data = called_args[1]
        assert insert_data["name"] == "new"
        assert insert_data["value"] == 100
        assert "created_at" in insert_data and "updated_at" in insert_data

    @pytest.mark.asyncio
    async def test_create_entity_with_existing_id(
        self, concrete_repository, mock_provider,
    ):
        """Test creating an entity that already has an ID"""
        entity = concrete_repository._row_to_entity(
            {"id": 456, "name": "existing", "value": 200},
        )

        insert_result = Mock()
        insert_result.success = True
        insert_result.inserted_id = 456
        mock_provider.execute_insert.return_value = insert_result

        result = await concrete_repository.create(entity)

        assert result.id == 456
        # Should still include ID in insert data since it's not None
        called_args = mock_provider.execute_insert.call_args[0]
        assert called_args[0] == "test_entities"
        insert_data = called_args[1]
        assert insert_data["id"] == 456
        assert insert_data["name"] == "existing"
        assert insert_data["value"] == 200
        assert "created_at" in insert_data and "updated_at" in insert_data

    @pytest.mark.asyncio
    async def test_update_entity(self, concrete_repository, mock_provider):
        """Test updating an existing entity"""
        entity = concrete_repository._row_to_entity(
            {"id": 1, "name": "updated", "value": 300},
        )

        update_result = Mock()
        update_result.success = True
        mock_provider.execute_update.return_value = update_result

        result = await concrete_repository.update(entity)

        assert result == entity

        called_args = mock_provider.execute_update.call_args[0]
        assert called_args[0] == "test_entities"
        update_data = called_args[1]
        assert update_data["name"] == "updated"
        assert update_data["value"] == 300
        assert "updated_at" in update_data
        assert called_args[2] == '"id" = ?'
        assert called_args[3] == [1]

    @pytest.mark.asyncio
    async def test_update_entity_without_id(self, concrete_repository):
        """Test updating entity without ID raises error"""
        entity = concrete_repository._row_to_entity({"name": "no_id", "value": 400})

        with pytest.raises(
            RepositoryError, match="Entity must have a primary key value for update",
        ):
            await concrete_repository.update(entity)

    @pytest.mark.asyncio
    async def test_delete_entity(self, concrete_repository, mock_provider):
        """Test deleting an entity"""
        entity = concrete_repository._row_to_entity(
            {"id": 1, "name": "to_delete", "value": 500},
        )

        delete_result = Mock()
        delete_result.success = True
        mock_provider.execute_delete.return_value = delete_result

        await concrete_repository.delete(entity)

        mock_provider.execute_delete.assert_called_once_with(
            "test_entities", '"id" = ?', [1],
        )

    @pytest.mark.asyncio
    async def test_delete_entity_without_id(self, concrete_repository):
        """Test deleting entity without ID raises error"""
        entity = concrete_repository._row_to_entity({"name": "no_id", "value": 600})

        with pytest.raises(
            RepositoryError, match="Entity must have a primary key value for deletion",
        ):
            await concrete_repository.delete(entity)

    @pytest.mark.asyncio
    async def test_delete_by_id(self, concrete_repository, mock_provider):
        """Test deleting entity by ID"""
        delete_result = Mock()
        delete_result.success = True
        mock_provider.execute_delete.return_value = delete_result

        await concrete_repository.delete_by_id(42)

        mock_provider.execute_delete.assert_called_once_with(
            "test_entities", '"id" = ?', [42],
        )

    # Error handling tests
