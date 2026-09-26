"""Tests for join/aggregate/CTE/window/set-operation builders (full SQL rendering)."""

from __future__ import annotations

from quadkit.sql.query.sql_builder import AsyncQueryBuilder
from quadkit.sql.query.sql_types import JoinType


def _b() -> AsyncQueryBuilder:
    return AsyncQueryBuilder("users")


class TestJoinRendering:
    def test_inner_join_default(self) -> None:
        q = _b().join("posts", "users.id = posts.user_id").build()
        assert "INNER JOIN" in q.sql and "posts" in q.sql

    def test_left_join(self) -> None:
        q = _b().join("posts", "u.id = p.user_id", JoinType.LEFT).build()
        assert "LEFT JOIN posts ON u.id = p.user_id" in q.sql

    def test_multiple_joins(self) -> None:
        q = (
            _b()
            .join("posts", "u.id = p.user_id", JoinType.LEFT)
            .join("comments", "p.id = c.post_id", JoinType.INNER)
            .build()
        )
        assert q.sql.count("JOIN") == 2

    def test_join_chaining_returns_self(self) -> None:
        b = _b()
        assert b.join("posts", "a = b") is b


class TestGroupAggregateRendering:
    def test_group_by_having(self) -> None:
        q = _b().select_count().group_by("dept").having("count", ">", 5).build()
        assert "GROUP BY" in q.sql and "HAVING" in q.sql

    def test_having_with_operator_enum(self) -> None:
        from quadkit.sql.query.operators import Operator

        q = _b().group_by("dept").having("cnt", Operator.GE, 3).build()
        assert "HAVING" in q.sql

    def test_having_multiple_anded(self) -> None:
        q = (
            _b()
            .group_by("dept")
            .having("a", ">", 1)
            .having("b", "<", 9)
            .build()
        )
        assert q.sql.count(" AND ") >= 1 or " AND ".join(["", ""]) in q.sql

    def test_count_star_default_alias(self) -> None:
        q = _b().select_count().build()
        assert 'COUNT(*) AS "count"' in q.sql or "COUNT(*) AS count" in q.sql

    def test_count_custom_alias(self) -> None:
        q = _b().select_count("id", alias="users").build()
        assert "COUNT(" in q.sql and "users" in q.sql

    def test_sum_avg_min_max_default_aliases(self) -> None:
        assert "SUM(" in _b().select_sum("salary").build().sql
        q = _b().select_sum("salary", alias="pay").build()
        assert "pay" in q.sql
        assert "_avg" in _b().select_avg("salary").build().sql
        assert "_min" in _b().select_min("salary").build().sql
        assert "_max" in _b().select_max("salary").build().sql


class TestRawExpressions:
    def test_select_raw(self) -> None:
        q = _b().select_raw("COALESCE(nickname, name) AS display_name").build()
        assert "COALESCE(nickname, name) AS display_name" in q.sql

    def test_order_by_raw(self) -> None:
        q = _b().order_by_raw("CASE WHEN priority = 1 THEN 0 ELSE 1 END").build()
        assert "ORDER BY" in q.sql and "CASE WHEN" in q.sql


class TestCTERendering:
    def test_cte(self) -> None:
        q = _b().with_cte("active", "SELECT * FROM users WHERE active = true").build()
        assert q.sql.startswith("WITH ") and "active AS" in q.sql

    def test_recursive_cte(self) -> None:
        q = _b().with_recursive_cte("tree", "SELECT 1").build()
        assert q.sql.startswith("WITH RECURSIVE")

    def test_mixed_ctes(self) -> None:
        q = _b().with_cte("a", "SELECT 1").with_recursive_cte("b", "SELECT 2").build()
        assert q.sql.startswith("WITH RECURSIVE")


class TestWindowRendering:
    def test_window_basic(self) -> None:
        q = _b().select_window("ROW_NUMBER()", alias="rn").build()
        assert "ROW_NUMBER()" in q.sql and "OVER" in q.sql and "rn" in q.sql

    def test_window_partition_order(self) -> None:
        q = _b().select_window(
            "SUM(revenue)",
            partition_by=["region", "year"],
            order_by="month",
            alias="total",
        ).build()
        assert "PARTITION BY" in q.sql and "ORDER BY" in q.sql

    def test_window_default_alias_from_func(self) -> None:
        q = _b().select_window("RANK() OVER ()").build()
        assert "rank" in q.sql.lower()


class TestSetOperationRendering:
    def test_union(self) -> None:
        q = _b().select("name").union("SELECT name FROM admins").build()
        assert "UNION" in q.sql and "SELECT name FROM admins" in q.sql

    def test_union_all(self) -> None:
        q = _b().union_all("SELECT name FROM x").build()
        assert "UNION ALL" in q.sql

    def test_intersect_except(self) -> None:
        assert "INTERSECT" in _b().intersect("SELECT 1").build().sql
        assert "EXCEPT" in _b().except_("SELECT 1").build().sql

    def test_multiple_set_ops_chained(self) -> None:
        q = _b().union("SELECT 1").union_all("SELECT 2").build()
        assert q.sql.count("UNION") >= 2


class TestCompositeQuery:
    def test_full_pipeline_sql(self) -> None:
        q = (
            _b()
            .with_cte("a", "SELECT 1 AS id")
            .select("name")
            .select_count("id", alias="n")
            .join("posts", "users.id = posts.uid", JoinType.LEFT)
            .where("active", "=", True)
            .group_by("dept")
            .having("n", ">", 1)
            .order_by("name", desc=False)
            .limit(10)
            .build()
        )
        sql = q.sql
        for fragment in ("WITH ", "LEFT JOIN", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT"):
            assert fragment in sql, fragment
