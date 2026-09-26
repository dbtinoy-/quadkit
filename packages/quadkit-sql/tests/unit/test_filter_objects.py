#!/usr/bin/env python3
"""Unit tests for typed SQL filter objects."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.contracts.data import DatabaseProviderProtocol
import quadkit.sql as quadkit_sql
from quadkit.sql import GenericRepository


class TestFilterObjectExports:
    """Test public exports for typed SQL filters."""

    def test_root_namespace_exports_filter_builders(self) -> None:
        """Root namespace should expose typed filter builders."""
        assert hasattr(quadkit_sql, "F")
        assert hasattr(quadkit_sql, "field")

    def test_filter_field_is_column_quoted(self) -> None:
        """Filter field must render as a quoted Column, never raw."""
        sql, params = (quadkit_sql.F("status") == "active").to_sql()
        assert sql == '"status" = ?'
        assert params == ["active"]


class TestTypedRepositoryFilters:
    """Test typed filters in repository entry points."""

    @pytest.fixture
    def mock_provider(self) -> Mock:
        """Create a mocked database provider."""
        provider = Mock(spec=DatabaseProviderProtocol)
        provider.execute_query = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        return provider

    @pytest.fixture
    def repository(self, mock_provider: Mock) -> GenericRepository[dict[str, Any], int]:
        """Create a generic repository for typed-filter tests."""
        return GenericRepository[dict[str, Any], int](
            provider=mock_provider,
            table_name="users",
            entity_class=dict,
            key_field="id",
        )

    @pytest.mark.asyncio
    async def test_find_many_accepts_typed_filters(
        self, repository: GenericRepository[dict[str, Any], int], mock_provider: Mock
    ) -> None:
        """find_many should translate typed filters into SQL predicates."""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "age": 21, "status": "active"}]
        mock_provider.execute_query.return_value = query_result

        results = await repository.find_many(
            quadkit_sql.F("age") > 18,
            quadkit_sql.F("status").in_(["active", "pending"]),
        )

        assert results == [{"id": 1, "age": 21, "status": "active"}]
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "users" WHERE "age" > ? AND "status" IN (?, ?)',
            [18, "active", "pending"],
        )

    @pytest.mark.asyncio
    async def test_find_one_accepts_composed_filter(
        self, repository: GenericRepository[dict[str, Any], int], mock_provider: Mock
    ) -> None:
        """find_one should support AND-composed typed filters."""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 1, "name": "john", "status": "active"}]
        mock_provider.execute_query.return_value = query_result

        result = await repository.find_one(
            (quadkit_sql.F("status") == "active")
            & quadkit_sql.F("name").ilike("%john%")
        )

        assert result == {"id": 1, "name": "john", "status": "active"}
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "users" WHERE ("status" = ? AND "name" ILIKE ?) LIMIT 1',
            ["active", "%john%"],
        )

    @pytest.mark.asyncio
    async def test_count_accepts_typed_filter(
        self, repository: GenericRepository[dict[str, Any], int], mock_provider: Mock
    ) -> None:
        """count should support typed filters."""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"count": 2}]
        mock_provider.execute_query.return_value = query_result

        result = await repository.count(quadkit_sql.F("status") == "active")

        assert result == 2
        mock_provider.execute_query.assert_called_once_with(
            'SELECT COUNT(*) as count FROM "users" WHERE "status" = ?',
            ["active"],
        )

    @pytest.mark.asyncio
    async def test_generic_find_accepts_typed_filters(
        self, repository: GenericRepository[dict[str, Any], int], mock_provider: Mock
    ) -> None:
        """GenericRepository.find should forward typed filters."""
        query_result = Mock()
        query_result.success = True
        query_result.rows = [{"id": 3, "status": "active"}]
        mock_provider.execute_query.return_value = query_result

        results = await repository.find(filters=quadkit_sql.F("status") == "active")

        assert results == [{"id": 3, "status": "active"}]
        mock_provider.execute_query.assert_called_once_with(
            'SELECT * FROM "users" WHERE "status" = ?',
            ["active"],
        )
