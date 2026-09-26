"""SQL identifier validation for the events SQL stores.

Stores interpolate ``table_name`` into SQL at identifier positions, where
parameter binding cannot substitute.  :func:`validate_table_name` enforces
identifier shape at construction time so no unvalidated value is ever
interpolated (the regex mirrors ``quadkit-sql``'s
``backup.backup_manager._validate_table_name``; it cannot be imported
here because ``quadkit-events`` must not depend on ``quadkit-sql``).
"""

from __future__ import annotations

import re

MAX_SQL_IDENTIFIER_LENGTH = 63

SQL_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def validate_table_name(table_name: str) -> None:
    """Validate that ``table_name`` is a safe SQL identifier.

    Accepted names match ``[a-zA-Z_][a-zA-Z0-9_]*`` and are at most
    ``MAX_SQL_IDENTIFIER_LENGTH`` characters long (Postgres' identifier
    limit).

    Args:
        table_name: Unqualified table name that will be interpolated
            into SQL statements.

    Raises:
        ValueError: If the name does not match the identifier pattern or
            exceeds the maximum length.
    """
    if len(table_name) > MAX_SQL_IDENTIFIER_LENGTH:
        msg = (
            f"Invalid table name: {table_name!r}. "
            f"Table names must be at most {MAX_SQL_IDENTIFIER_LENGTH} characters."
        )
        raise ValueError(msg)
    if not SQL_IDENTIFIER_PATTERN.fullmatch(table_name):
        msg = (
            f"Invalid table name: {table_name!r}. "
            "Table names must match pattern [a-zA-Z_][a-zA-Z0-9_]*"
        )
        raise ValueError(msg)
