"""Value types for data access contracts."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from enum import StrEnum
from typing import Any, Literal, TypeAlias

__all__ = [
    "AndExpr",
    "CursorPaginationSpec",
    "FieldContains",
    "FieldEq",
    "FieldGt",
    "FieldGte",
    "FieldIn",
    "FieldLt",
    "FieldLte",
    "FieldNeq",
    "FilterExpression",
    "LogicalOperator",
    "NotExpr",
    "OrExpr",
    "PaginationSpec",
    "ProjectionSpec",
    "SortSpecification",
]


class LogicalOperator(StrEnum):
    """Logical combination operator for filter groups."""

    AND = "and"
    OR = "or"


@dataclass(frozen=True)
class FieldEq:
    """Equality predicate: ``field == value``."""

    field: str
    value: Any


@dataclass(frozen=True)
class FieldGt:
    """Greater-than predicate: ``field > value``."""

    field: str
    value: Any


@dataclass(frozen=True)
class FieldLt:
    """Less-than predicate: ``field < value``."""

    field: str
    value: Any


@dataclass(frozen=True)
class FieldGte:
    """Greater-than-or-equal predicate: ``field >= value``."""

    field: str
    value: Any


@dataclass(frozen=True)
class FieldLte:
    """Less-than-or-equal predicate: ``field <= value``."""

    field: str
    value: Any


@dataclass(frozen=True)
class FieldNeq:
    """Not-equal predicate: ``field != value``."""

    field: str
    value: Any


@dataclass(frozen=True)
class FieldContains:
    """Substring predicate: ``value in field``."""

    field: str
    value: Any


@dataclass(frozen=True)
class FieldIn:
    """Membership predicate: ``field in values``."""

    field: str
    values: tuple[Any, ...]


@dataclass(frozen=True)
class AndExpr:
    """Logical conjunction of two filter expressions."""

    left: FilterExpression
    right: FilterExpression


@dataclass(frozen=True)
class OrExpr:
    """Logical disjunction of two filter expressions."""

    left: FilterExpression
    right: FilterExpression


@dataclass(frozen=True)
class NotExpr:
    """Logical negation of a filter expression."""

    expr: FilterExpression


FilterExpression: TypeAlias = (
    FieldEq
    | FieldGt
    | FieldGte
    | FieldLt
    | FieldLte
    | FieldNeq
    | FieldContains
    | FieldIn
    | AndExpr
    | OrExpr
    | NotExpr
)
"""Composable predicate tree for repository queries.

Build expressions using the concrete leaf/node types:

    >>> expr = AndExpr(FieldEq("status", "active"), FieldGt("age", 18))
"""


# ---------------------------------------------------------------------------
# Sort specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SortSpecification:
    """Specifies ordering for a query result.

    Attributes:
        field: Name of the field to sort on.
        direction: Sort direction — ``"asc"`` or ``"desc"``.
    """

    field: str
    direction: Literal["asc", "desc"] = "asc"


# ---------------------------------------------------------------------------
# Pagination specifications
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PaginationSpec:
    """Offset-based pagination parameters.

    Attributes:
        page: 1-based page number.
        size: Number of results per page.
    """

    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        """Zero-based offset for the current page."""
        return (self.page - 1) * self.size


@dataclass(frozen=True)
class CursorPaginationSpec:
    """Cursor-based (keyset) pagination parameters.

    Attributes:
        cursor: Opaque cursor string returned from a previous response.
        size: Number of results per page.
    """

    cursor: str | None = None
    size: int = 20


# ---------------------------------------------------------------------------
# ProjectionProtocol specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectionSpec:
    """Describes which fields to include or exclude from query results.

    Attributes:
        include: Explicit set of field names to return.
        exclude: Names of fields to omit from the result.
    """

    include: frozenset[str] = dc_field(default_factory=frozenset)
    exclude: frozenset[str] = dc_field(default_factory=frozenset)
