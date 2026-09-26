"""Query builder type definitions.

Dataclasses and enums used by the query builder for representing
SQL clauses, conditions, and query parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.sql.sql_dialect import SQLDialect

if TYPE_CHECKING:
    from quadkit.contracts.data.identifiers import Column
    from quadkit.sql.query.operators import Operator


class JoinType(StrEnum):
    """SQL JOIN types.

    Attributes:
        INNER: INNER JOIN
        LEFT: LEFT JOIN
        RIGHT: RIGHT JOIN
        FULL: FULL OUTER JOIN
    """

    INNER = "INNER"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FULL = "FULL"


class ConflictAction(StrEnum):
    """Action to take on INSERT conflict."""

    DO_NOTHING = "DO NOTHING"
    DO_UPDATE = "DO UPDATE"


class LockMode(StrEnum):
    """Row-level locking modes."""

    FOR_UPDATE = "FOR UPDATE"
    FOR_SHARE = "FOR SHARE"
    FOR_NO_KEY_UPDATE = "FOR NO KEY UPDATE"
    FOR_KEY_SHARE = "FOR KEY SHARE"


class SetOperationType(StrEnum):
    """Set operation types."""

    UNION = "UNION"
    UNION_ALL = "UNION ALL"
    INTERSECT = "INTERSECT"
    EXCEPT = "EXCEPT"


@dataclass
class Condition:
    """Represents a WHERE condition in a query.

    Attributes:
        column: The validated, quoted column.
        operator: The comparison operator.
        value: The value to compare against.
    """

    column: Column
    operator: Operator
    value: Any


@dataclass
class Join:
    """Represents a JOIN clause in a query.

    Attributes:
        table: The table to join with.
        on: The ON condition.
        type: The type of join (defaults to INNER).
    """

    table: str
    on: str
    type: JoinType = JoinType.INNER


@dataclass
class Order:
    """Represents an ORDER BY clause."""

    column: Column
    desc: bool = False


@dataclass
class GroupByClause:
    """Represents GROUP BY columns."""

    columns: list[str]


@dataclass
class HavingClause:
    """Represents a HAVING condition."""

    column: Column
    operator: Operator
    value: Any


@dataclass
class RawExpression:
    """A raw SQL expression with optional parameters."""

    sql: str
    params: list[Any] | None = None


@dataclass
class OrCondition:
    """Represents an OR WHERE condition."""

    column: Column
    operator: Operator
    value: Any


@dataclass
class CTEClause:
    """Represents a Common Table Expression (WITH clause)."""

    name: str
    query: str
    params: list[Any] | None = None
    recursive: bool = False


@dataclass
class WindowExpression:
    """Represents a window function expression."""

    func: str
    partition_by: list[Column] | None = None
    order_by: str | None = None
    alias: str = ""


@dataclass
class SetOperation:
    """Represents a set operation between queries."""

    operation: SetOperationType
    query: str
    params: list[Any] | None = None


@dataclass
class ParameterizedQuery:
    """A parameterized SQL query ready for execution."""

    sql: str
    params: tuple
    dialect: SQLDialect = SQLDialect.POSTGRESQL
