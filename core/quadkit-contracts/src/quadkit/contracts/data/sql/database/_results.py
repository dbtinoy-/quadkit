"""Result value types for database operations."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class IsolationLevel(StrEnum):
    """Standard SQL transaction isolation levels.

    These map directly to the ANSI SQL standard isolation levels.
    Drivers translate them to the appropriate driver-specific syntax.

    Note:
        Not all levels are supported by every database engine.
        SQLite maps levels to its ``DEFERRED``/``IMMEDIATE``/``EXCLUSIVE``
        semantics as a best-effort approximation.
    """

    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@dataclass(frozen=True)
class QueryResult:
    """Result of a database query.

    Implements the iterator and sequence protocols so that code expecting
    a plain ``list[dict]`` from a query result continues to work after the
    return type is normalised to ``QueryResult``.

    Example::

        result = await provider.execute_query("SELECT * FROM users")
        for row in result:          # iterate directly
            print(row["email"])
        if not result:              # bool coercion
            raise LookupError("no rows")
        first = result[0]           # index access
        rows = list(result)         # convert to plain list
    """

    rows: list[dict[str, Any]]
    row_count: int
    execution_time: float
    success: bool
    error_message: str | None = None

    # ------------------------------------------------------------------
    # Sequence-like helpers
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[dict[str, Any]]:
        """Iterate over query rows."""
        return iter(self.rows)

    def __len__(self) -> int:
        """Return the number of rows in the result."""
        return len(self.rows)

    def __bool__(self) -> bool:
        """Return ``True`` when the query succeeded and returned at least one row."""
        return self.success and bool(self.rows)

    def __getitem__(self, index: int) -> dict[str, Any]:
        """Return the row at *index*.

        Args:
            index: Zero-based row index.

        Returns:
            Row dict at the requested index.
        """
        return self.rows[index]


@dataclass(frozen=True)
class InsertResult:
    """Result of an insert operation."""

    inserted_id: Any | None
    affected_rows: int
    execution_time: float
    success: bool
    error_message: str | None = None


@dataclass(frozen=True)
class UpdateResult:
    """Result of an update operation."""

    affected_rows: int
    execution_time: float
    success: bool
    error_message: str | None = None


@dataclass(frozen=True)
class DeleteResult:
    """Result of a delete operation."""

    affected_rows: int
    execution_time: float
    success: bool
    error_message: str | None = None
