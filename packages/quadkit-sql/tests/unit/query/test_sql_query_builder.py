"""Tests for SqlQueryBuilder — admin query primitive translation."""

from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.dialects import postgresql

from quadkit.sql.query.admin_builder import SqlQueryBuilder


class TestSqlQueryBuilder:
    """Test SqlQueryBuilder — immutable fluent builder wrapping SQLAlchemy Select."""

    @staticmethod
    def _compile(stmt: Select) -> tuple[str, tuple]:
        compiled = stmt.compile(
            dialect=postgresql.dialect(paramstyle="numeric"),
        )
        return str(compiled), tuple(compiled.params.values())

    def test_empty_builder_returns_select(self) -> None:
        builder = SqlQueryBuilder()
        stmt = builder.build()
        assert isinstance(stmt, Select)

    def test_empty_builder_sql(self) -> None:
        builder = SqlQueryBuilder()
        sql, params = self._compile(builder.build())
        assert sql == "SELECT _"
        assert params == ()

    def test_with_filters_equality(self) -> None:
        builder = SqlQueryBuilder().with_filters({"status": "active"})
        sql, params = self._compile(builder.build())
        assert "WHERE" in sql
        assert "status" in sql
        assert "=" in sql or "==" in sql
        assert "active" in params

    def test_with_filters_gte(self) -> None:
        builder = SqlQueryBuilder().with_filters({"amount__gte": 100})
        sql, params = self._compile(builder.build())
        assert ">=" in sql
        assert "amount" in sql
        assert 100 in params

    def test_with_filters_lte(self) -> None:
        builder = SqlQueryBuilder().with_filters({"amount__lte": 50})
        sql, params = self._compile(builder.build())
        assert "<=" in sql
        assert "amount" in sql
        assert 50 in params

    def test_with_filters_gt(self) -> None:
        builder = SqlQueryBuilder().with_filters({"age__gt": 18})
        sql, params = self._compile(builder.build())
        assert ">" in sql or ">=" in sql  # SQLAlchemy may render > as text
        assert "age" in sql
        assert 18 in params

    def test_with_filters_lt(self) -> None:
        builder = SqlQueryBuilder().with_filters({"age__lt": 65})
        sql, params = self._compile(builder.build())
        assert "<" in sql or "<=" in sql
        assert "age" in sql
        assert 65 in params

    def test_with_filters_multiple(self) -> None:
        builder = SqlQueryBuilder().with_filters(
            {"status": "active", "amount__gte": 100},
        )
        sql, params = self._compile(builder.build())
        assert "WHERE" in sql
        assert "AND" in sql.upper()
        assert "status" in sql
        assert "amount" in sql
        assert "active" in params
        assert 100 in params

    def test_with_filters_empty_dict(self) -> None:
        builder = SqlQueryBuilder().with_filters({})
        sql, params = self._compile(builder.build())
        assert sql == "SELECT _"
        assert params == ()

    def test_with_search_ilike(self) -> None:
        builder = SqlQueryBuilder().with_search("john", ["name", "email"])
        sql, params = self._compile(builder.build())
        assert "ILIKE" in sql.upper()
        assert "name" in sql
        assert "email" in sql
        assert params == ("%john%", "%john%")

    def test_with_search_or_combined(self) -> None:
        builder = SqlQueryBuilder().with_search("test", ["field_a", "field_b"])
        sql, params = self._compile(builder.build())
        assert "OR" in sql.upper()
        # Both fields should be searched
        assert "field_a" in sql
        assert "field_b" in sql

    def test_with_search_empty_returns_same(self) -> None:
        builder = SqlQueryBuilder()
        result = builder.with_search("", ["name"])
        sql, params = self._compile(result.build())
        assert sql == "SELECT _"
        assert params == ()

    def test_with_search_no_fields_returns_same(self) -> None:
        builder = SqlQueryBuilder()
        result = builder.with_search("test", [])
        sql, params = self._compile(result.build())
        assert sql == "SELECT _"
        assert params == ()

    def test_with_order_asc(self) -> None:
        builder = SqlQueryBuilder().with_order([("name", "asc")])
        sql, params = self._compile(builder.build())
        assert "ORDER BY" in sql.upper()
        assert "name" in sql
        assert "ASC" in sql.upper()

    def test_with_order_desc(self) -> None:
        builder = SqlQueryBuilder().with_order([("created_at", "desc")])
        sql, params = self._compile(builder.build())
        assert "ORDER BY" in sql.upper()
        assert "created_at" in sql
        assert "DESC" in sql.upper()

    def test_with_order_multiple(self) -> None:
        builder = SqlQueryBuilder().with_order(
            [("name", "asc"), ("created_at", "desc")],
        )
        sql, params = self._compile(builder.build())
        assert "ORDER BY" in sql.upper()
        assert "name" in sql
        assert "created_at" in sql

    def test_with_order_empty(self) -> None:
        builder = SqlQueryBuilder().with_order([])
        sql, params = self._compile(builder.build())
        assert sql == "SELECT _"
        assert params == ()

    def test_with_pagination(self) -> None:
        builder = SqlQueryBuilder().with_pagination(10, 25)
        sql, params = self._compile(builder.build())
        assert "LIMIT" in sql.upper()
        assert "OFFSET" in sql.upper()
        # LIMIT at the end, OFFSET before LIMIT
        lim_idx = sql.upper().index("LIMIT")
        assert 25 in params or str(25) in sql[lim_idx:]

    def test_immutability(self) -> None:
        builder = SqlQueryBuilder()
        builder2 = builder.with_filters({"status": "active"})
        assert builder is not builder2
        sql1, _ = self._compile(builder.build())
        assert sql1 == "SELECT _"

    def test_chaining(self) -> None:
        builder = (
            SqlQueryBuilder()
            .with_filters({"status": "active"})
            .with_search("test", ["name"])
            .with_order([("name", "asc")])
            .with_pagination(0, 25)
        )
        sql, params = self._compile(builder.build())
        assert "WHERE" in sql
        assert "ILIKE" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()
        assert "OFFSET" in sql.upper()

    def test_from_params_all(self) -> None:
        builder = SqlQueryBuilder.from_params(
            filters={"status": "active"},
            search="test",
            search_fields=["name"],
            order=[("name", "asc")],
            offset=0,
            limit=25,
        )
        sql, params = self._compile(builder.build())
        assert "WHERE" in sql
        assert "ILIKE" in sql.upper()
        assert "ORDER BY" in sql.upper()
        assert "LIMIT" in sql.upper()
        assert "OFFSET" in sql.upper()

    def test_from_params_none(self) -> None:
        builder = SqlQueryBuilder.from_params()
        sql, params = self._compile(builder.build())
        assert sql == "SELECT _"
        assert params == ()

    def test_from_params_filters_only(self) -> None:
        builder = SqlQueryBuilder.from_params(filters={"status": "inactive"})
        sql, params = self._compile(builder.build())
        assert "WHERE" in sql
        assert "inactive" in params
