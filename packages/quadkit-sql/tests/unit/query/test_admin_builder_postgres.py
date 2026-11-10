"""Unit tests for ``SqlQueryBuilder.compile_postgres_where``."""

from __future__ import annotations

from quadkit.sql.query import SqlQueryBuilder


def test_compile_postgres_where_empty() -> None:
    where_sql, params, next_idx = SqlQueryBuilder().compile_postgres_where()
    assert where_sql == ""
    assert params == []
    assert next_idx == 1


def test_compile_postgres_where_filters_and_search() -> None:
    builder = SqlQueryBuilder.from_params(
        filters={"status": "published", "score__gte": 5},
        search="rabies",
        search_fields=["title", "summary"],
    )
    where_sql, params, next_idx = builder.compile_postgres_where()
    assert "$1" in where_sql
    assert "$2" in where_sql
    assert "$3" in where_sql
    assert "$4" in where_sql
    assert "ILIKE" in where_sql
    assert params == ["published", 5, "%rabies%", "%rabies%"]
    assert next_idx == 5


def test_compile_postgres_where_table_alias_and_uuid_casts() -> None:
    builder = SqlQueryBuilder.from_params(
        filters={"urgency_level": "HIGH"},
        search="abc",
        search_fields=["id", "user_id", "symptoms"],
    )
    where_sql, params, next_idx = builder.compile_postgres_where(
        table_alias="a",
        uuid_text_fields=("id", "user_id"),
    )
    assert "a.urgency_level = $1" in where_sql
    assert "a.id::text ILIKE $2" in where_sql
    assert "a.user_id::text ILIKE $3" in where_sql
    assert "a.symptoms ILIKE $4" in where_sql
    assert params == ["HIGH", "%abc%", "%abc%", "%abc%"]
    assert next_idx == 5
