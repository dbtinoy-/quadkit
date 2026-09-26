"""Repository error-handling paths."""

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
    async def test_find_all_failure(self, concrete_repository, mock_provider):
        """Test find_many with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("query failed")

        with pytest.raises(RepositoryError, match="Failed to find entities with criteria"):
            await concrete_repository.find_many()

    @pytest.mark.asyncio
    async def test_find_many_failure(self, concrete_repository, mock_provider):
        """Test find_many with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("query failed")

        with pytest.raises(
            RepositoryError, match="Failed to find entities with criteria",
        ):
            await concrete_repository.find_many(name="test")

    @pytest.mark.asyncio
    async def test_exists_failure(self, concrete_repository, mock_provider):
        """Test exists with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("query failed")

        with pytest.raises(
            RepositoryError, match="Failed to check existence with criteria",
        ):
            await concrete_repository.exists(name="test")

    @pytest.mark.asyncio
    async def test_count_failure(self, concrete_repository, mock_provider):
        """Test count with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("query failed")

        with pytest.raises(
            RepositoryError, match="Failed to count entities with criteria",
        ):
            await concrete_repository.count(name="test")

    @pytest.mark.asyncio
    async def test_create_failure(self, concrete_repository, mock_provider):
        """Test create with database failure"""
        entity = concrete_repository._row_to_entity({"name": "fail", "value": 700})
        mock_provider.execute_insert.side_effect = DatabaseError("insert failed")

        with pytest.raises(RepositoryError, match="Failed to create entity"):
            await concrete_repository.create(entity)

    @pytest.mark.asyncio
    async def test_update_failure(self, concrete_repository, mock_provider):
        """Test update with database failure"""
        entity = concrete_repository._row_to_entity(
            {"id": 1, "name": "fail", "value": 800},
        )
        mock_provider.execute_update.side_effect = DatabaseError("update failed")

        with pytest.raises(RepositoryError, match="Failed to update entity"):
            await concrete_repository.update(entity)

    @pytest.mark.asyncio
    async def test_delete_failure(self, concrete_repository, mock_provider):
        """Test delete with database failure"""
        entity = concrete_repository._row_to_entity(
            {"id": 1, "name": "fail", "value": 900},
        )
        mock_provider.execute_delete.side_effect = DatabaseError("delete failed")

        with pytest.raises(RepositoryError, match="Failed to delete entity"):
            await concrete_repository.delete(entity)

    @pytest.mark.asyncio
    async def test_find_all_query_failure(self, concrete_repository, mock_provider):
        """Test find_many when query fails"""
        query_result = Mock()
        query_result.success = False
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many()

        assert results == []

    @pytest.mark.asyncio
    async def test_find_many_query_failure(self, concrete_repository, mock_provider):
        """Test find_many when query fails"""
        query_result = Mock()
        query_result.success = False
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many(name="test")

        assert results == []

    @pytest.mark.asyncio
    async def test_exists_no_rows(self, concrete_repository, mock_provider):
        """Test exists when query succeeds but returns no rows"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.exists(name="test")

        assert result is False

    @pytest.mark.asyncio
    async def test_count_no_rows(self, concrete_repository, mock_provider):
        """Test count when query succeeds but returns no rows"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.count(name="test")

        assert result == 0

    @pytest.mark.asyncio
    async def test_create_without_inserted_id(self, concrete_repository, mock_provider):
        """Test create when insert succeeds but no inserted_id"""
        entity = concrete_repository._row_to_entity({"name": "no_id", "value": 100})

        insert_result = Mock()
        insert_result.success = True
        insert_result.inserted_id = None
        mock_provider.execute_insert.return_value = insert_result

        result = await concrete_repository.create(entity)

        assert result == entity
        assert result.id is None  # Should remain None

    @pytest.mark.asyncio
    async def test_update_query_failure(self, concrete_repository, mock_provider):
        """Test update when query fails"""
        entity = concrete_repository._row_to_entity(
            {"id": 1, "name": "fail", "value": 200},
        )

        update_result = Mock()
        update_result.success = False
        update_result.error_message = "update failed"
        mock_provider.execute_update.return_value = update_result

        with pytest.raises(RepositoryError, match="Update failed: update failed"):
            await concrete_repository.update(entity)

    @pytest.mark.asyncio
    async def test_delete_query_failure(self, concrete_repository, mock_provider):
        """Test delete when query fails"""
        entity = concrete_repository._row_to_entity(
            {"id": 1, "name": "fail", "value": 300},
        )

        delete_result = Mock()
        delete_result.success = False
        delete_result.error_message = "delete failed"
        mock_provider.execute_delete.return_value = delete_result

        with pytest.raises(RepositoryError, match="Delete failed: delete failed"):
            await concrete_repository.delete(entity)

    @pytest.mark.asyncio
    async def test_delete_by_id_query_failure(self, concrete_repository, mock_provider):
        """Test delete_by_id when query fails"""
        delete_result = Mock()
        delete_result.success = False
        delete_result.error_message = "delete failed"
        mock_provider.execute_delete.return_value = delete_result

        with pytest.raises(RepositoryError, match="Delete failed: delete failed"):
            await concrete_repository.delete_by_id(1)

    @pytest.mark.asyncio
    async def test_bulk_create(self, concrete_repository, mock_provider):
        """Test default bulk_create implementation"""
        entities = [
            concrete_repository._row_to_entity({"name": "first", "value": 1}),
            concrete_repository._row_to_entity({"name": "second", "value": 2}),
        ]
        
        insert_results = [Mock(success=True, inserted_id=1), Mock(success=True, inserted_id=2)]
        mock_provider.execute_insert.side_effect = insert_results
        
        results = await concrete_repository.bulk_create(entities)
        
        assert len(results) == 2
        assert results[0].id == 1
        assert results[1].id == 2
        assert mock_provider.execute_insert.call_count == 2

    @pytest.mark.asyncio
    async def test_paginate(self, concrete_repository, mock_provider):
        """Test default paginate implementation"""
        query_result = Mock(success=True)
        query_result.rows = [{"id": 1, "name": "first", "value": 1}]
        mock_provider.execute_query.side_effect = [
            query_result,  # for find_many
            Mock(success=True, rows=[{"count": 5}])  # for count
        ]
        
        result = await concrete_repository.paginate(page=2, per_page=2, status="active")
        
        assert result["total"] == 5
        assert result["page"] == 2
        assert result["per_page"] == 2
        assert result["total_pages"] == 3
        assert len(result["data"]) == 1
        assert result["data"][0].id == 1
