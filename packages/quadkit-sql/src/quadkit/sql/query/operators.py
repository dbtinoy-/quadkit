"""Query builder operator definitions.

SQL comparison operators, their handler implementations, and the
operator registry used by the query builder.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol


class Operator(StrEnum):
    """SQL comparison operators for query conditions."""

    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    IN = "IN"
    NOT_IN = "NOT IN"
    LIKE = "LIKE"
    ILIKE = "ILIKE"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    BETWEEN = "BETWEEN"
    NOT_BETWEEN = "NOT BETWEEN"


class QueryOperator(Protocol):
    """Protocol for query operator handlers."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]: ...


class EqualityOperator:
    """Handler for equality operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} = ${param_idx}", [value], param_idx + 1)


class NotEqualOperator:
    """Handler for not-equal operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} != ${param_idx}", [value], param_idx + 1)


class LessThanOperator:
    """Handler for less-than operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} < ${param_idx}", [value], param_idx + 1)


class LessThanOrEqualOperator:
    """Handler for less-than-or-equal operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} <= ${param_idx}", [value], param_idx + 1)


class GreaterThanOperator:
    """Handler for greater-than operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} > ${param_idx}", [value], param_idx + 1)


class GreaterThanOrEqualOperator:
    """Handler for greater-than-or-equal operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} >= ${param_idx}", [value], param_idx + 1)


class InOperator:
    """Handler for IN operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        if not value:
            return ("1=0", [], param_idx)
        placeholders = ", ".join(
            f"${i}" for i in range(param_idx, param_idx + len(value))
        )
        return (
            f"{column} IN ({placeholders})",
            list(value),
            param_idx + len(value),
        )


class NotInOperator:
    """Handler for NOT IN operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        if not value:
            return ("1=1", [], param_idx)
        placeholders = ", ".join(
            f"${i}" for i in range(param_idx, param_idx + len(value))
        )
        return (
            f"{column} NOT IN ({placeholders})",
            list(value),
            param_idx + len(value),
        )


class LikeOperator:
    """Handler for LIKE operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} LIKE ${param_idx}", [value], param_idx + 1)


class ILikeOperator:
    """Handler for ILIKE operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} ILIKE ${param_idx}", [value], param_idx + 1)


class IsNullOperator:
    """Handler for IS NULL operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} IS NULL", [], param_idx)


class IsNotNullOperator:
    """Handler for IS NOT NULL operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        return (f"{column} IS NOT NULL", [], param_idx)


class BetweenOperator:
    """Handler for BETWEEN operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        low, high = value
        return (
            f"{column} BETWEEN ${param_idx} AND ${param_idx + 1}",
            [low, high],
            param_idx + 2,
        )


class NotBetweenOperator:
    """Handler for NOT BETWEEN operator."""

    def apply(
        self,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        low, high = value
        return (
            f"{column} NOT BETWEEN ${param_idx} AND ${param_idx + 1}",
            [low, high],
            param_idx + 2,
        )


class QueryOperatorRegistry:
    """Registry for query operator handlers.

    Maintains a mapping of Operator enum values to handler implementations
    that can generate SQL fragments and collect parameters.
    """

    def __init__(self) -> None:
        """Initialize the registry with default operators."""
        self._operators: dict[Operator, QueryOperator] = {}
        self._register_default_operators()

    def _register_default_operators(self) -> None:
        """Register default query operators."""
        self.register_operator(Operator.EQ, EqualityOperator())
        self.register_operator(Operator.NE, NotEqualOperator())
        self.register_operator(Operator.LT, LessThanOperator())
        self.register_operator(Operator.LE, LessThanOrEqualOperator())
        self.register_operator(Operator.GT, GreaterThanOperator())
        self.register_operator(Operator.GE, GreaterThanOrEqualOperator())
        self.register_operator(Operator.IN, InOperator())
        self.register_operator(Operator.NOT_IN, NotInOperator())
        self.register_operator(Operator.LIKE, LikeOperator())
        self.register_operator(Operator.ILIKE, ILikeOperator())
        self.register_operator(Operator.IS_NULL, IsNullOperator())
        self.register_operator(Operator.IS_NOT_NULL, IsNotNullOperator())
        self.register_operator(Operator.BETWEEN, BetweenOperator())
        self.register_operator(Operator.NOT_BETWEEN, NotBetweenOperator())

    def register_operator(self, op: Operator, handler: QueryOperator) -> None:
        """Register a query operator handler.

        Args:
            op: The Operator enum value.
            handler: The handler implementing the operator logic.
        """
        self._operators[op] = handler

    def apply_operator(
        self,
        op: Operator,
        column: str,
        value: Any,
        param_idx: int,
    ) -> tuple[str, list[Any], int]:
        """Apply an operator to a column and value.

        Args:
            op: The operator to apply.
            column: The column name.
            value: The value to compare against.
            param_idx: The starting parameter index.

        Returns:
            Tuple of (sql_fragment, params, next_param_idx).
        """
        handler = self._operators.get(op)
        if handler:
            return handler.apply(column, value, param_idx)
        return (f"{column} = ${param_idx}", [value], param_idx + 1)
