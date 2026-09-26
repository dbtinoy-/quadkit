"""GenericRepository read operations."""

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


    @pytest.mark.asyncio
    async def test_find_by_id_success(self, pydantic_repository, mock_provider):
        """Test finding entity by ID successfully"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "test", "value": 42}]
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.find_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.name == "test"
        assert result.value == 42

        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE "id" = ?', [1],
        )

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(self, pydantic_repository, mock_provider):
        """Test finding entity by ID when not found"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.find_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_id_failure(self, pydantic_repository, mock_provider):
        """Test finding entity by ID with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("database error")

        with pytest.raises(RepositoryError, match="Failed to find entity by id 1"):
            await pydantic_repository.find_by_id(1)

    # Test find_one
    @pytest.mark.asyncio
    async def test_find_one_success(self, pydantic_repository, mock_provider):
        """Test finding one entity with criteria"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "test", "value": 42}]
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.find_one(name="test", value=42)

        assert result is not None
        assert result.name == "test"
        assert result.value == 42

        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE "name" = ? AND "value" = ? LIMIT 1',
            ["test", 42],
        )

    @pytest.mark.asyncio
    async def test_find_one_not_found(self, pydantic_repository, mock_provider):
        """Test finding one entity when not found"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.find_one(name="nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_one_failure(self, pydantic_repository, mock_provider):
        """Test finding one entity with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("database error")

        with pytest.raises(RepositoryError, match="Failed to find entity"):
            await pydantic_repository.find_one(name="test")

    # Test find_many
    @pytest.mark.asyncio
    async def test_find_many_success(self, pydantic_repository, mock_provider):
        """Test finding many entities with criteria"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [
            {"id": 1, "name": "test", "value": 42},
            {"id": 2, "name": "test", "value": 43},
        ]
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many(name="test")

        assert len(results) == 2
        assert results[0].name == "test"
        assert results[1].name == "test"

        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE "name" = ?', ["test"],
        )

    @pytest.mark.asyncio
    async def test_find_many_no_criteria(self, pydantic_repository, mock_provider):
        """Test finding many entities with no criteria"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "all", "value": 1}]
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many()

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1', None,
        )

    @pytest.mark.asyncio
    async def test_find_many_failure(self, pydantic_repository, mock_provider):
        """Test finding many entities with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("database error")

        with pytest.raises(
            RepositoryError, match="Failed to find entities with criteria",
        ):
            await pydantic_repository.find_many(name="test")

    # Test find_many
    @pytest.mark.asyncio
    async def test_find_all_no_limits(self, pydantic_repository, mock_provider):
        """Test finding all entities without limits"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [
            {"id": 1, "name": "first", "value": 10},
            {"id": 2, "name": "second", "value": 20},
        ]
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many()

        assert len(results) == 2
        assert results[0].id == 1
        assert results[1].id == 2

        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1', None,
        )

    @pytest.mark.asyncio
    async def test_find_all_with_limit(self, pydantic_repository, mock_provider):
        """Test finding all entities with limit"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "first", "value": 10}]
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many(limit=1)

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1 LIMIT ?', [1],
        )

    @pytest.mark.asyncio
    async def test_find_all_with_offset(self, pydantic_repository, mock_provider):
        """Test finding all entities with offset"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 2, "name": "second", "value": 20}]
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many(offset=1)

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1 OFFSET ?', [1],
        )

    @pytest.mark.asyncio
    async def test_find_all_with_limit_and_offset(
        self, pydantic_repository, mock_provider,
    ):
        """Test finding all entities with both limit and offset"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 2, "name": "second", "value": 20}]
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many(limit=1, offset=1)

        assert len(results) == 1
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "test_entities" WHERE 1=1 LIMIT ? OFFSET ?', [1, 1],
        )

    @pytest.mark.asyncio
    async def test_find_many_query_failure(self, pydantic_repository, mock_provider):
        """Test find_many when query fails"""
        query_result = Mock()
        query_result.success = False
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many(name="test")

        assert results == []

    @pytest.mark.asyncio
    async def test_find_all_query_failure(self, pydantic_repository, mock_provider):
        """Test find_many when query fails"""
        query_result = Mock()
        query_result.success = False
        query_result.rows = []
        mock_provider.execute_query.return_value = query_result

        results = await pydantic_repository.find_many()

        assert results == []

    @pytest.mark.asyncio
    async def test_find_all_exception(self, pydantic_repository, mock_provider):
        """Test find_many when execute_query raises exception"""
        mock_provider.execute_query.side_effect = DatabaseError("database error")

        with pytest.raises(RepositoryError, match="Failed to find entities"):
            await pydantic_repository.find_many()

    # Test create
