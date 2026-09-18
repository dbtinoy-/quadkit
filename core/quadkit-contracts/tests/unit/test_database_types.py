"""Tests for database contracts types."""

import pytest

from quadkit.contracts.data.sql.database import (
    IsolationLevel,
    QueryResult,
)


class TestIsolationLevel:
    """Tests for IsolationLevel enum."""

    def test_isolation_level_values(self) -> None:
        """Test IsolationLevel enum values."""
        assert IsolationLevel.READ_UNCOMMITTED.value == "READ UNCOMMITTED"
        assert IsolationLevel.READ_COMMITTED.value == "READ COMMITTED"
        assert IsolationLevel.REPEATABLE_READ.value == "REPEATABLE READ"
        assert IsolationLevel.SERIALIZABLE.value == "SERIALIZABLE"

    def test_isolation_level_members(self) -> None:
        """Test IsolationLevel has expected members."""
        members = list(IsolationLevel)
        assert len(members) == 4


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_query_result_creation(self) -> None:
        """Test creating QueryResult."""
        result = QueryResult(
            rows=[{"id": 1, "name": "Alice"}],
            row_count=1,
            execution_time=0.05,
            success=True,
        )
        assert result.rows[0]["name"] == "Alice"
        assert result.row_count == 1
        assert result.success is True

    def test_query_result_iteration(self) -> None:
        """Test QueryResult iteration."""
        result = QueryResult(
            rows=[{"id": 1}, {"id": 2}],
            row_count=2,
            execution_time=0.01,
            success=True,
        )
        rows = list(result)
        assert len(rows) == 2

    def test_query_result_len(self) -> None:
        """Test QueryResult length."""
        result = QueryResult(
            rows=[{"id": 1}, {"id": 2}, {"id": 3}],
            row_count=3,
            execution_time=0.01,
            success=True,
        )
        assert len(result) == 3

    def test_query_result_bool_true(self) -> None:
        """Test QueryResult bool when has rows."""
        result = QueryResult(
            rows=[{"id": 1}],
            row_count=1,
            execution_time=0.01,
            success=True,
        )
        assert bool(result) is True

    def test_query_result_bool_false_empty(self) -> None:
        """Test QueryResult bool when empty."""
        result = QueryResult(
            rows=[],
            row_count=0,
            execution_time=0.01,
            success=True,
        )
        assert bool(result) is False

    def test_query_result_bool_false_failed(self) -> None:
        """Test QueryResult bool when failed."""
        result = QueryResult(
            rows=[],
            row_count=0,
            execution_time=0.01,
            success=False,
            error_message="Syntax error",
        )
        assert bool(result) is False

    def test_query_result_getitem(self) -> None:
        """Test QueryResult index access."""
        result = QueryResult(
            rows=[{"id": 1}, {"id": 2}],
            row_count=2,
            execution_time=0.01,
            success=True,
        )
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2
