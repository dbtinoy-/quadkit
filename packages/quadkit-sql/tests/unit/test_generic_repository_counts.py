"""GenericRepository count and exists tests."""

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


    async def test_count_with_criteria(self, pydantic_repository, mock_provider):
        """Test counting entities with criteria"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 5}]
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.count(status="active")

        assert result == 5

        mock_provider.execute_query.assert_called_once_with(
            'SELECT COUNT(*) as count FROM "test_entities" WHERE "status" = ?', ["active"],
        )

    @pytest.mark.asyncio
    async def test_count_with_filters_dict(self, pydantic_repository, mock_provider):
        """Test counting entities with dict-style filters (mirrors find())"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 3}]
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.count(filters={"status": "active"})

        assert result == 3

        mock_provider.execute_query.assert_called_once_with(
            'SELECT COUNT(*) as count FROM "test_entities" WHERE "status" = ?', ["active"],
        )

    @pytest.mark.asyncio
    async def test_count_no_criteria(self, pydantic_repository, mock_provider):
        """Test counting all entities"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 10}]
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.count()

        assert result == 10

        mock_provider.execute_query.assert_called_once_with(
            'SELECT COUNT(*) as count FROM "test_entities"', [],
        )

    @pytest.mark.asyncio
    async def test_count_no_rows(self, pydantic_repository, mock_provider):
        """Test count when query succeeds but returns no rows"""
        query_result = QueryResult(
            rows=[], row_count=0, execution_time=0.01, success=True,
        )
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.count(name="test")

        assert result == 0

    # Test exists
    @pytest.mark.asyncio
    async def test_exists_true(self, pydantic_repository, mock_provider):
        """Test checking existence when entity exists"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 1}]
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.exists(name="test")

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, pydantic_repository, mock_provider):
        """Test checking existence when entity doesn't exist"""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 0}]
        mock_provider.execute_query.return_value = query_result

        result = await pydantic_repository.exists(name="nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_failure(self, pydantic_repository, mock_provider):
        """Test exists with database failure"""
        mock_provider.execute_query.side_effect = DatabaseError("database error")

        with pytest.raises(
            RepositoryError, match="Failed to check existence with criteria",
        ):
            await pydantic_repository.exists(name="test")
