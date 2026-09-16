"""SQL identifier exceptions.

This module contains only exception types for SQL identifier handling.
The concrete identifier implementations have been moved to the optional provider.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import ValidationError


class InvalidIdentifierError(ValidationError):
    """Raised when an SQL identifier fails validation.

    Attributes:
        identifier: The offending identifier string.
    """

    _code = "QK_ERR_DB_010"

    def __init__(
        self, message: str, identifier: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(
            message=message,
            details={"identifier": identifier},
            **kwargs,
        )
        self.identifier = identifier


# Placeholder for RawSQL type that may be used elsewhere
class RawSQL:
    """Raw SQL string that bypasses validation.

    This is a marker type for SQL that should not be validated or quoted.

    Warning:
        Never pass user-supplied values directly into this query string.
        Always use parameterized queries or the provided binding mechanisms
        to prevent SQL injection vulnerabilities.

    Attributes:
        sql: The raw SQL string.
    """

    __slots__ = ("_sql",)

    def __init__(self, sql: str) -> None:
        self._sql = sql

    def __str__(self) -> str:
        return self._sql

    def __repr__(self) -> str:
        return f"RawSQL({self._sql!r})"


__all__ = [
    "InvalidIdentifierError",
    "RawSQL",
]
