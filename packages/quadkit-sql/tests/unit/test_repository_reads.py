"""Repository read operations: find/exists/count."""

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
    async def test_repository_initialization(self, concrete_repository, mock_provider):
        """Test repository initialization"""
        assert concrete_repository.provider == mock_provider
        assert concrete_repository.table_name == "test_entities"
        assert concrete_repository.key_field == "id"

    @pytest.mark.asyncio
    async def test_find_by_id_success(self, concrete_repository, mock_provider):
        """Test finding entity by ID successfully"""
        # Mock successful query result
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "test", "value": 42}]
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.find_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "test"
        assert result.value == 42

        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE "id" = ?', [1],
        )

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, concrete_repository, mock_provider):
        """Test finding entity by ID when not found"""
        # Mock empty result
        query_result = Mock()
        query_result.success = True
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.find_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_id_failure(self, concrete_repository, mock_provider):
        """Test finding entity by ID with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("database error")

        with pytest.raises(RepositoryError, match="Failed to find entity by id 1"):
            await concrete_repository.find_by_id(1)

    @pytest.mark.asyncio
    async def test_find_all_no_limits(self, concrete_repository, mock_provider):
        """Test finding all entities without limits"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [
            {"id": 1, "name": "first", "value": 10},
            {"id": 2, "name": "second", "value": 20},
        ]
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many()

        assert len(results) == 2
        assert results[0].id == 1
        assert results[1].id == 2

        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1', None,
        )

    @pytest.mark.asyncio
    async def test_find_all_with_limit(self, concrete_repository, mock_provider):
        """Test finding all entities with limit"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "first", "value": 10}]
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many(limit=1)

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1 LIMIT ?', [1],
        )

    @pytest.mark.asyncio
    async def test_find_all_with_offset(self, concrete_repository, mock_provider):
        """Test finding all entities with offset"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 2, "name": "second", "value": 20}]
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many(offset=1)

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1 OFFSET ?', [1],
        )

    @pytest.mark.asyncio
    async def test_find_all_with_limit_and_offset(
        self, concrete_repository, mock_provider,
    ):
        """Test finding all entities with both limit and offset"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 2, "name": "second", "value": 20}]
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many(limit=1, offset=1)

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1 LIMIT ? OFFSET ?', [1, 1],
        )

    @pytest.mark.asyncio
    async def test_find_many_with_criteria(self, concrete_repository, mock_provider):
        """Test finding entities with criteria"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "test", "value": 42}]
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many(name="test", value=42)

        assert len(results) == 1
        assert results[0].name == "test"

        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE "name" = ? AND "value" = ?', ["test", 42],
        )

    @pytest.mark.asyncio
    async def test_find_many_no_criteria(self, concrete_repository, mock_provider):
        """Test finding entities with no criteria"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "all", "value": 1}]
        mock_provider.execute_query.return_value = query_result

        results = await concrete_repository.find_many()

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1', None,
        )

    @pytest.mark.asyncio
    async def test_find_one_with_results(self, concrete_repository, mock_provider):
        """Test finding one entity when results exist"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "first", "value": 10}]
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.find_one(name="first")

        assert result is not None
        assert result.name == "first"

    @pytest.mark.asyncio
    async def test_find_one_no_results(self, concrete_repository, mock_provider):
        """Test finding one entity when no results"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.find_one(name="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_exists_true(self, concrete_repository, mock_provider):
        """Test checking existence when entity exists"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 1}]
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.exists(name="test")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, concrete_repository, mock_provider):
        """Test checking existence when entity doesn't exist"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 0}]
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.exists(name="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_count_with_criteria(self, concrete_repository, mock_provider):
        """Test counting entities with criteria"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 5}]
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.count(status="active")

        assert result == 5

    @pytest.mark.asyncio
    async def test_count_no_criteria(self, concrete_repository, mock_provider):
        """Test counting all entities"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 10}]
        mock_provider.execute_query.return_value = query_result

        result = await concrete_repository.count()

        assert result == 10

