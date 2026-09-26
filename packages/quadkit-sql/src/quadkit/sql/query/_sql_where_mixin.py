"""Where-clause mixin for AsyncQueryBuilder: all WHERE condition methods."""

from __future__ import annotations

from typing import Any, Self

from quadkit.contracts.data.identifiers import Column
from quadkit.sql.query.operators import Operator
from quadkit.sql.query.sql_types import (
    Condition,
    OrCondition,
    RawExpression,
)


class _WhereMixin:
    """WHERE condition methods for AsyncQueryBuilder."""

    def where(self, column: str, op: Operator | str, value: Any = None) -> Self:
        """Add a WHERE condition.

        Args:
            column: The column name.
            op: The operator (Operator enum or string).
            value: The value to compare against.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.where("status", Operator.EQ, "active")
            >>> builder.where("age", Operator.GT, 18)
            >>> builder.where("role", Operator.IN, ["admin", "editor"])
        """
        if isinstance(op, str):
            op = Operator(op)

        if value is None and op not in (Operator.IS_NULL, Operator.IS_NOT_NULL):
            if op == Operator.EQ:
                op = Operator.IS_NULL
            elif op == Operator.NE:
                op = Operator.IS_NOT_NULL

        self._wheres.append(Condition(Column(column), op, value))  # type: ignore[attr-defined]
        return self

    def where_raw(self, expression: str, params: list[Any] | None = None) -> Self:
        """Add a raw SQL WHERE clause.

        Example:
            >>> builder.where_raw("age > $1 AND age < $2", [18, 65])

        Note:
            Escape hatch: ``expression`` is passed through verbatim. Never
            interpolate user input into it — always use parameter
            placeholders with ``params``.
        """
        self._raw_wheres.append(RawExpression(expression, params))  # type: ignore[attr-defined]
        return self

    def or_where(self, column: str, op: Operator | str, value: Any) -> Self:
        """Add an OR WHERE condition.

        Example:
            >>> builder.where("status", Operator.EQ, "active").or_where("role", Operator.EQ, "admin")
        """
        if isinstance(op, str):
            op = Operator(op)
        self._or_wheres.append(OrCondition(Column(column), op, value))  # type: ignore[attr-defined]
        return self

    def where_between(self, column: str, low: Any, high: Any) -> Self:
        """Add a BETWEEN condition.

        Example:
            >>> builder.where_between("age", 18, 65)
        """
        self._wheres.append(Condition(Column(column), Operator.BETWEEN, (low, high)))  # type: ignore[attr-defined]
        return self

    def where_not_between(self, column: str, low: Any, high: Any) -> Self:
        """Add a NOT BETWEEN condition."""
        self._wheres.append(  # type: ignore[attr-defined]
            Condition(Column(column), Operator.NOT_BETWEEN, (low, high))
        )
        return self

    def where_if(
        self, condition: bool, column: str, op: Operator | str, value: Any
    ) -> Self:
        """Conditionally add a WHERE clause.

        Example:
            >>> builder.where_if(user_id is not None, "user_id", Operator.EQ, user_id)
        """
        if condition:
            return self.where(column, op, value)
        return self

    def where_in_subquery(
        self,
        column: str,
        subquery: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add WHERE column IN (subquery).

        Example:
            >>> builder.where_in_subquery(
            ...     "user_id",
            ...     "SELECT id FROM users WHERE active = $1",
            ...     [True],
            ... )
        """
        sql = f"{Column(column)} IN ({subquery})"
        self._subquery_wheres.append(RawExpression(sql, params))  # type: ignore[attr-defined]
        return self

    def where_not_in_subquery(
        self,
        column: str,
        subquery: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add WHERE column NOT IN (subquery)."""
        sql = f"{Column(column)} NOT IN ({subquery})"
        self._subquery_wheres.append(RawExpression(sql, params))  # type: ignore[attr-defined]
        return self

    def where_exists(
        self,
        subquery: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add WHERE EXISTS (subquery).

        Example:
            >>> builder.where_exists(
            ...     "SELECT 1 FROM orders WHERE orders.user_id = users.id",
            ... )
        """
        sql = f"EXISTS ({subquery})"
        self._subquery_wheres.append(RawExpression(sql, params))  # type: ignore[attr-defined]
        return self

    def where_not_exists(
        self,
        subquery: str,
        params: list[Any] | None = None,
    ) -> Self:
        """Add WHERE NOT EXISTS (subquery)."""
        sql = f"NOT EXISTS ({subquery})"
        self._subquery_wheres.append(RawExpression(sql, params))  # type: ignore[attr-defined]
        return self
