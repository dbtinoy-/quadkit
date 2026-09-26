"""GenericRepository init and entity<->row mapping tests."""

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


    def test_repository_initialization(self, pydantic_repository, mock_provider):
        """Test repository initialization"""
        assert pydantic_repository.provider == mock_provider
        assert pydantic_repository.table_name == "test_entities"
        assert pydantic_repository.key_field == "id"
        assert pydantic_repository.entity_class == SampleEntity

    def test_repository_initialization_accepts_rls_policy(self, mock_provider):
        """GenericRepository should forward an RLS policy to SQLRepository."""
        policy = RowLevelSecurityPolicy(columns=[ScopeColumn("tenant_id")])
        repo = GenericRepository[SampleEntity, int](
            provider=mock_provider,
            table_name="test_entities",
            entity_class=SampleEntity,
            key_field="id",
            rls_policy=policy,
        )

        assert repo._rls_policy is policy

    # Test _entity_to_dict method
    def test_entity_to_dict_pydantic(self, pydantic_repository):
        """Test converting Pydantic entity to dict"""
        entity = SampleEntity(id=1, name="test", value=42)
        result = pydantic_repository._entity_to_dict(entity)
        assert result == {"id": 1, "name": "test", "value": 42}

    def test_entity_to_dict_regular_class(self, regular_repository):
        """Test converting regular class entity to dict"""
        entity = SampleEntityRegular(id=1, name="test", value=42)
        result = regular_repository._entity_to_dict(entity)
        assert result == {"id": 1, "name": "test", "value": 42}

    def test_entity_to_dict_dict_entity(self, dict_repository):
        """Test converting dict entity to dict"""
        entity = {"key": "test_key", "name": "test", "value": 42}
        result = dict_repository._entity_to_dict(entity)
        assert result == {"key": "test_key", "name": "test", "value": 42}

    def test_entity_to_dict_invalid_entity(self, pydantic_repository):
        """Test converting invalid entity raises error"""
        entity = "invalid_entity"
        with pytest.raises(RepositoryError, match="Cannot convert entity of type"):
            pydantic_repository._entity_to_dict(entity)

    # Test _row_to_entity method
    def test_row_to_entity_pydantic(self, pydantic_repository):
        """Test converting row to Pydantic entity"""
        row = {"id": 1, "name": "test", "value": 42}
        entity = pydantic_repository._row_to_entity(row)
        assert isinstance(entity, SampleEntity)
        assert entity.id == 1
        assert entity.name == "test"
        assert entity.value == 42

    def test_row_to_entity_regular_class(self, regular_repository):
        """Test converting row to regular class entity"""
        row = {"id": 1, "name": "test", "value": 42}
        entity = regular_repository._row_to_entity(row)
        assert isinstance(entity, SampleEntityRegular)
        assert entity.id == 1
        assert entity.name == "test"
        assert entity.value == 42

    def test_row_to_entity_dict(self, dict_repository):
        """Test converting row to dict entity"""
        row = {"key": "test_key", "name": "test", "value": 42}
        entity = dict_repository._row_to_entity(row)
        assert isinstance(entity, dict)
        assert entity == {"key": "test_key", "name": "test", "value": 42}

    # Test find_by_id
