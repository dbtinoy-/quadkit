"""GenericRepository write operations."""

from __future__ import annotations

from dataclasses import dataclass
#!/usr/bin/env python3
"""Unit tests for GenericRepository"""

from typing import Any
from unittest.mock import AsyncMock, Mock

from quadkit.domain import DomainModel
import pytest

from quadkit.contracts.data import DatabaseProviderProtocol, QueryResult, UpdateResult
from quadkit.sql.exceptions import DatabaseError, RepositoryError
from quadkit.sql.repositories.generic_repository import GenericRepository
from quadkit.sql.row_level_security import RowLevelSecurityPolicy, ScopeColumn


@dataclass
class SampleEntity(DomainModel):
    """Test Pydantic entity"""

    id: int | None = None
    name: str = ""
    value: int = 0


class SampleEntityRegular:
    """Test regular class entity"""

    def __init__(self, id=None, name="", value=0):
        self.id = id
        self.name = name
        self.value = value



class TestGenericRepository:
    """Test GenericRepository functionality"""

    @pytest.fixture
    def mock_provider(self):
        """Mock database provider"""
        provider = Mock(spec=DatabaseProviderProtocol)
        provider.execute_query = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        return provider

    @pytest.fixture
    def pydantic_repository(self, mock_provider):
        """Create repository for Pydantic entities"""
        return GenericRepository[SampleEntity, int](
            provider=mock_provider,
            table_name="test_entities",
            entity_class=SampleEntity,
            key_field="id",
        )

    @pytest.fixture
    def regular_repository(self, mock_provider):
        """Create repository for regular class entities"""
        return GenericRepository[SampleEntityRegular, int](
            provider=mock_provider,
            table_name="test_entities",
            entity_class=SampleEntityRegular,
            key_field="id",
        )

    @pytest.fixture
    def dict_repository(self, mock_provider):
        """Create repository for dict entities"""
        return GenericRepository[dict[str, Any], str](
            provider=mock_provider,
            table_name="test_entities",
            entity_class=dict,
            key_field="key",
        )


    async def test_create_new_entity_pydantic(self, pydantic_repository, mock_provider):
        """Test creating a new Pydantic entity"""
        entity = SampleEntity(name="new", value=100)

        insert_result = Mock()
        insert_result.success = True
        insert_result.inserted_id = 123
        mock_provider.execute_insert.return_value = insert_result

        result = await pydantic_repository.create(entity)

        assert result.id == 123
        assert result.name == "new"
        assert result.value == 100

        called_args = mock_provider.execute_insert.call_args[0]
        assert called_args[0] == "test_entities"
        insert_data = called_args[1]
        assert insert_data["name"] == "new"
        assert insert_data["value"] == 100
        assert "created_at" in insert_data and "updated_at" in insert_data

    @pytest.mark.asyncio
    async def test_create_entity_with_existing_id(
        self, pydantic_repository, mock_provider,
    ):
        """Test creating an entity that already has an ID"""
        entity = SampleEntity(id=456, name="existing", value=200)

        insert_result = Mock()
        insert_result.success = True
        insert_result.inserted_id = 456
        mock_provider.execute_insert.return_value = insert_result

        result = await pydantic_repository.create(entity)

        assert result.id == 456
        # Note: ID is included in insert data since it's not None
        called_args = mock_provider.execute_insert.call_args[0]
        assert called_args[0] == "test_entities"
        insert_data = called_args[1]
        assert insert_data["id"] == 456
        assert insert_data["name"] == "existing"
        assert insert_data["value"] == 200
        assert "created_at" in insert_data and "updated_at" in insert_data

    @pytest.mark.asyncio
    async def test_create_regular_class_entity(self, regular_repository, mock_provider):
        """Test creating a regular class entity"""
        entity = SampleEntityRegular(name="regular", value=300)

        insert_result = Mock()
        insert_result.success = True
        insert_result.inserted_id = 789
        mock_provider.execute_insert.return_value = insert_result

        result = await regular_repository.create(entity)

        assert result.id == 789
        assert result.name == "regular"
        assert result.value == 300

    @pytest.mark.asyncio
    async def test_create_dict_entity(self, dict_repository, mock_provider):
        """Test creating a dict entity"""
        entity = {"name": "dict_entity", "value": 400}

        insert_result = Mock()
        insert_result.success = True
        insert_result.inserted_id = "new_key"
        mock_provider.execute_insert.return_value = insert_result

        result = await dict_repository.create(entity)

        assert result["key"] == "new_key"
        assert result["name"] == "dict_entity"
        assert result["value"] == 400

    @pytest.mark.asyncio
    async def test_create_failure(self, pydantic_repository, mock_provider):
        """Test create with database failure"""
        entity = SampleEntity(name="fail", value=500)
        mock_provider.execute_insert.side_effect = DatabaseError("insert failed")

        with pytest.raises(RepositoryError, match="Failed to create entity"):
            await pydantic_repository.create(entity)

    # Test update
    @pytest.mark.asyncio
    async def test_update_entity_pydantic(self, pydantic_repository, mock_provider):
        """Test updating a Pydantic entity"""
        entity = SampleEntity(id=1, name="updated", value=600)

        update_result = Mock()
        update_result.success = True
        mock_provider.execute_update.return_value = update_result

        result = await pydantic_repository.update(entity)

        assert result == entity

        called_args = mock_provider.execute_update.call_args[0]
        assert called_args[0] == "test_entities"
        update_data = called_args[1]
        assert update_data["name"] == "updated"
        assert update_data["value"] == 600
        assert "updated_at" in update_data
        assert called_args[2] == '"id" = ?'
        assert called_args[3] == [1]

    @pytest.mark.asyncio
    async def test_update_entity_without_id(self, pydantic_repository):
        """Test updating entity without ID raises error"""
        entity = SampleEntity(name="no_id", value=700)

        with pytest.raises(
            RepositoryError, match="Entity must have a primary key value for update",
        ):
            await pydantic_repository.update(entity)

    @pytest.mark.asyncio
    async def test_update_query_failure(self, pydantic_repository, mock_provider):
        """Test update when query fails"""
        entity = SampleEntity(id=1, name="fail", value=200)

        update_result = Mock()
        update_result.success = False
        update_result.error_message = "update failed"
        mock_provider.execute_update.return_value = update_result

        with pytest.raises(RepositoryError, match="Update failed: update failed"):
            await pydantic_repository.update(entity)

    # Test delete
    @pytest.mark.asyncio
    async def test_delete_entity_success(self, pydantic_repository, mock_provider):
        """Test deleting an entity successfully"""
        delete_result = Mock()
        delete_result.success = True
        delete_result.affected_rows = 1
        mock_provider.execute_delete.return_value = delete_result

        result = await pydantic_repository.delete(1)

        assert result is True

        mock_provider.execute_delete.assert_called_once_with(
            "test_entities", '"id" = ?', [1],
        )

    @pytest.mark.asyncio
    async def test_delete_entity_not_found(self, pydantic_repository, mock_provider):
        """Test deleting an entity that doesn't exist"""
        delete_result = Mock()
        delete_result.success = True
        delete_result.affected_rows = 0
        mock_provider.execute_delete.return_value = delete_result

        result = await pydantic_repository.delete(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_failure(self, pydantic_repository, mock_provider):
        """Test delete with database failure"""
        mock_provider.execute_delete.side_effect = DatabaseError("delete failed")

        with pytest.raises(RepositoryError, match="Failed to delete entity"):
            await pydantic_repository.delete(1)

    # Test count
