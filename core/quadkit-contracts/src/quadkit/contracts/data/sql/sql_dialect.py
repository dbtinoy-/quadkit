"""SQL dialect enumeration for Quadkit.

Defines the supported SQL dialects and their identifier quoting conventions.
These are pure value types with no database dependencies, suitable for use
across all packages that need SQL identifier validation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class SQLDialect(StrEnum):
    """Supported SQL database dialects."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


# Maximum identifier lengths by dialect (from official documentation).
MAX_IDENTIFIER_LENGTHS: Final[dict[SQLDialect, int]] = {
    SQLDialect.POSTGRESQL: 63,
    SQLDialect.MYSQL: 64,
    SQLDialect.SQLITE: 128,
}

# Default max length used when dialect is unknown.
DEFAULT_MAX_IDENTIFIER_LENGTH: Final[int] = 63

__all__ = [
    "DEFAULT_MAX_IDENTIFIER_LENGTH",
    "MAX_IDENTIFIER_LENGTHS",
    "SQLDialect",
]
