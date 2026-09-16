"""Data access protocol class definitions."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from quadkit.contracts.data.types import (
    AndExpr as AndExpr,
)
from quadkit.contracts.data.types import (
    CursorPaginationSpec as CursorPaginationSpec,
)
from quadkit.contracts.data.types import (
    FieldContains as FieldContains,
)
from quadkit.contracts.data.types import (
    FieldEq as FieldEq,
)
from quadkit.contracts.data.types import (
    FieldGt as FieldGt,
)
from quadkit.contracts.data.types import (
    FieldGte as FieldGte,
)
from quadkit.contracts.data.types import (
    FieldIn as FieldIn,
)
from quadkit.contracts.data.types import (
    FieldLt as FieldLt,
)
from quadkit.contracts.data.types import (
    FieldLte as FieldLte,
)
from quadkit.contracts.data.types import (
    FieldNeq as FieldNeq,
)
from quadkit.contracts.data.types import (
    FilterExpression as FilterExpression,
)
from quadkit.contracts.data.types import (
    NotExpr as NotExpr,
)
from quadkit.contracts.data.types import (
    OrExpr as OrExpr,
)
from quadkit.contracts.data.types import (
    PaginationSpec as PaginationSpec,
)
from quadkit.contracts.data.types import (
    ProjectionSpec as ProjectionSpec,
)
from quadkit.contracts.data.types import (
    SortSpecification as SortSpecification,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

_T_co = TypeVar("_T_co", covariant=True)


@runtime_checkable
class QueryFilterProtocol(Protocol):
    """Simple query filter for data access.

    This is a simple field-value filter, not the full DDD SpecificationProtocol pattern.
    For composable specifications, use :class:`quadkit.contracts.domain.SpecificationProtocol`.
    """

    def __init__(self, field: str, value: Any) -> None:
        """Initialize filter.

        Args:
            field: Field name to filter on
            value: Value to filter by
        """
        ...


# ---------------------------------------------------------------------------
# Extension protocols (for data/ implementations)
# ---------------------------------------------------------------------------


@runtime_checkable
class FilterCompilerProtocol(Protocol, Generic[_T_co]):
    """Compiles a ``FilterExpression`` into a backend-specific query predicate.

    Type parameter ``T`` is the compiled representation — a Python callable
    for in-memory repositories, an SQL fragment for SQL backends, etc.
    """

    def compile(self, expression: FilterExpression) -> _T_co:
        """Compile *expression* into a backend query predicate.

        Args:
            expression: Filter expression to compile.

        Returns:
            A backend-specific predicate or query fragment.
        """
        ...


@runtime_checkable
class CursorCodecProtocol(Protocol):
    """Encodes and decodes opaque pagination cursor strings."""

    def encode(self, values: dict[str, Any]) -> str:
        """Encode *values* into an opaque cursor string.

        Args:
            values: Mapping of field names to their cursor values.

        Returns:
            An opaque cursor string.
        """
        ...

    def decode(self, cursor: str) -> dict[str, Any]:
        """Decode an opaque cursor string back to field values.

        Args:
            cursor: An opaque cursor string produced by :meth:`encode`.

        Returns:
            The original field-value mapping.
        """
        ...


@runtime_checkable
class PaginatorProtocol(Protocol, Generic[_T_co]):
    """Performs a single page of cursor-based pagination."""

    def paginate(
        self,
        *,
        cursor: str | None = None,
        size: int = 20,
        **kwargs: Any,
    ) -> Awaitable[Any]:
        """Fetch one page of results.

        Args:
            cursor: Opaque cursor from a previous page, or ``None`` for first.
            size: Number of results per page.
            **kwargs: Extra arguments forwarded to the fetch function.

        Returns:
            An awaitable resolving to a ``CursorPage[T]``.
        """
        ...


__all__ = [
    "AndExpr",
    "CursorCodecProtocol",
    "CursorPaginationSpec",
    "FieldContains",
    "FieldEq",
    "FieldGt",
    "FieldGte",
    "FieldIn",
    "FieldLt",
    "FieldLte",
    "FieldNeq",
    "FilterCompilerProtocol",
    "FilterExpression",
    "NotExpr",
    "OrExpr",
    "PaginationSpec",
    "PaginatorProtocol",
    "ProjectionSpec",
    "QueryFilterProtocol",
    "SortSpecification",
]
