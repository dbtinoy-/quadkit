"""Join and aggregate mixin for AsyncQueryBuilder: JOIN, GROUP BY, aggregates, CTEs, window functions, set operations."""

from __future__ import annotations

from typing import Any, Self

from quadkit.contracts.data.identifiers import Column
from quadkit.sql.query.operators import Operator
from quadkit.sql.query.sql_types import (
    CTEClause,
    HavingClause,
    Join,
    JoinType,
    RawExpression,
    SetOperation,
    SetOperationType,
    WindowExpression,
)


class _JoinAggregateMixin:
    """JOIN, GROUP BY, aggregate, CTE, window, and set-operation methods for AsyncQueryBuilder."""

    def join(self, table: str, on: str, join_type: JoinType = JoinType.INNER) -> Self:
        """Add a JOIN clause.

        Args:
            table: The table to join with.
            on: The ON condition (e.g., "users.id = posts.user_id").
            join_type: The type of join. Defaults to INNER.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.join("posts", "users.id = posts.user_id", JoinType.LEFT)
        """
        self._joins.append(Join(table, on, join_type))  # type: ignore[attr-defined]
        return self

    def group_by(self, *columns: str) -> Self:
        """Add GROUP BY columns.

        Example:
            >>> builder.select("department_id").select_count().group_by("department_id")
        """
        self._group_by.extend(Column(c) for c in columns)  # type: ignore[attr-defined]
        return self

    def having(self, column: str, op: Operator | str, value: Any) -> Self:
        """Add a HAVING condition (used with GROUP BY).

        Example:
            >>> builder.group_by("dept").having("count", Operator.GT, 5)
        """
        if isinstance(op, str):
            op = Operator(op)
        self._havings.append(HavingClause(Column(column), op, value))  # type: ignore[attr-defined]
        return self

    def select_count(self, column: str = "*", alias: str = "count") -> Self:
        """Add COUNT() to SELECT.

        Example:
            >>> builder.select_count()
            >>> builder.select_count("id", alias="user_count")
        """
        target = "*" if column == "*" else Column(column)
        self._raw_selects.append(RawExpression(f"COUNT({target}) AS {alias}"))  # type: ignore[attr-defined]
        return self

    def select_sum(self, column: str, alias: str | None = None) -> Self:
        """Add SUM() to SELECT."""
        col = Column(column)
        alias = alias or f"{col.name}_sum"
        self._raw_selects.append(RawExpression(f"SUM({col}) AS {alias}"))  # type: ignore[attr-defined]
        return self

    def select_avg(self, column: str, alias: str | None = None) -> Self:
        """Add AVG() to SELECT."""
        col = Column(column)
        alias = alias or f"{col.name}_avg"
        self._raw_selects.append(RawExpression(f"AVG({col}) AS {alias}"))  # type: ignore[attr-defined]
        return self

    def select_min(self, column: str, alias: str | None = None) -> Self:
        """Add MIN() to SELECT."""
        col = Column(column)
        alias = alias or f"{col.name}_min"
        self._raw_selects.append(RawExpression(f"MIN({col}) AS {alias}"))  # type: ignore[attr-defined]
        return self

    def select_max(self, column: str, alias: str | None = None) -> Self:
        """Add MAX() to SELECT."""
        col = Column(column)
        alias = alias or f"{col.name}_max"
        self._raw_selects.append(RawExpression(f"MAX({col}) AS {alias}"))  # type: ignore[attr-defined]
        return self

    def select_raw(self, expression: str, params: list[Any] | None = None) -> Self:
        """Add a raw SQL expression to SELECT.

        Example:
            >>> builder.select_raw("COALESCE(nickname, name) AS display_name")
        """
        self._raw_selects.append(RawExpression(expression, params))  # type: ignore[attr-defined]
        return self

    def order_by_raw(self, expression: str) -> Self:
        """Add a raw ORDER BY expression.

        Example:
            >>> builder.order_by_raw("CASE WHEN priority = 'high' THEN 0 ELSE 1 END")
        """
        self._raw_orders.append(expression)  # type: ignore[attr-defined]
        return self

    def with_cte(
        self,
        name: str,
        query: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add a CTE (WITH clause).

        Example:
            >>> builder.with_cte(
            ...     "active_users",
            ...     "SELECT * FROM users WHERE active = $1",
            ...     [True],
            ... ).select("*")
        """
        self._ctes.append(CTEClause(name, query, params))  # type: ignore[attr-defined]
        return self

    def with_recursive_cte(
        self,
        name: str,
        query: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add a recursive CTE (WITH RECURSIVE clause).

        Example:
            >>> builder.with_recursive_cte(
            ...     "org_tree",
            ...     "SELECT * FROM orgs WHERE parent_id IS NULL "
            ...     "UNION ALL "
            ...     "SELECT o.* FROM orgs o JOIN org_tree t ON o.parent_id = t.id",
            ... )
        """
        self._ctes.append(CTEClause(name, query, params, recursive=True))  # type: ignore[attr-defined]
        return self

    def select_window(
        self,
        func: str,
        *,
        partition_by: str | list[str] | None = None,
        order_by: str | None = None,
        alias: str | None = None,
    ) -> Self:
        """Add a window function to SELECT.

        Example:
            >>> builder.select_window(
            ...     "ROW_NUMBER()",
            ...     partition_by="department_id",
            ...     order_by="salary DESC",
            ...     alias="rank",
            ... )
            >>> builder.select_window(
            ...     "SUM(revenue)",
            ...     partition_by=["region", "year"],
            ...     order_by="month",
            ...     alias="running_total",
            ... )
        """
        if isinstance(partition_by, str):
            partition_by = [partition_by]
        partition_cols: list[Column] | None = None
        if partition_by:
            partition_cols = [Column(p) for p in partition_by]
        alias = alias or func.split("(", maxsplit=1)[0].lower()
        self._windows.append(  # type: ignore[attr-defined]
            WindowExpression(func, partition_cols, order_by, alias),
        )
        return self

    def union(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add UNION (deduped).

        Example:
            >>> builder.select("name").union("SELECT name FROM admins")
        """
        self._set_operations.append(  # type: ignore[attr-defined]
            SetOperation(SetOperationType.UNION, query, params),
        )
        return self

    def union_all(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add UNION ALL (with duplicates)."""
        self._set_operations.append(  # type: ignore[attr-defined]
            SetOperation(SetOperationType.UNION_ALL, query, params),
        )
        return self

    def intersect(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add INTERSECT."""
        self._set_operations.append(  # type: ignore[attr-defined]
            SetOperation(SetOperationType.INTERSECT, query, params),
        )
        return self

    def except_(
        self,
        query: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add EXCEPT."""
        self._set_operations.append(  # type: ignore[attr-defined]
            SetOperation(SetOperationType.EXCEPT, query, params),
        )
        return self
