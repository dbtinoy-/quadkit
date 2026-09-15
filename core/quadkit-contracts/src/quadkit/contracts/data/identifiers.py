"""Type-safe SQL identifier primitives.

Provides validated, dialect-aware SQL identifiers that can be safely
interpolated into SQL strings.  Any package building SQL queries
(``quadkit-sql``, ``quadkit-events``, ``quadkit-tasks``, ``quadkit-ai``,
…) can import directly from here without depending on each other.

Typical usage::

    from quadkit.contracts.data.identifiers import Table, Column, table, column

    t = table("users")
    c = column("email")
    query = f"SELECT {c} FROM {t} WHERE {c} = $1"
"""

from __future__ import annotations

from functools import lru_cache
import re
from typing import Final

from quadkit.contracts.data.sql.sql import InvalidIdentifierError
from quadkit.contracts.data.sql.sql_dialect import (
    DEFAULT_MAX_IDENTIFIER_LENGTH,
    MAX_IDENTIFIER_LENGTHS,
    SQLDialect,
)

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

_IDENT_RE: Final[re.Pattern[str]] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_RESERVED_WORDS: Final[frozenset[str]] = frozenset(
    {
        "ABORT",
        "ADD",
        "ALL",
        "ALTER",
        "ANALYZE",
        "AND",
        "AS",
        "ASC",
        "BEGIN",
        "BETWEEN",
        "BY",
        "CASCADE",
        "CASE",
        "CHECK",
        "COLLATE",
        "COLUMN",
        "COMMIT",
        "CONFLICT",
        "CONSTRAINT",
        "CREATE",
        "CROSS",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "CURRENT_TIMESTAMP",
        "DATABASE",
        "DEFAULT",
        "DELETE",
        "DESC",
        "DISTINCT",
        "DO",
        "DROP",
        "ELSE",
        "END",
        "ESCAPE",
        "EXCEPT",
        "EXCLUDED",
        "EXISTS",
        "EXPLAIN",
        "FALSE",
        "FOR",
        "FOREIGN",
        "FROM",
        "FULL",
        "FUNCTION",
        "GRANT",
        "GROUP",
        "HAVING",
        "IF",
        "IN",
        "INDEX",
        "INNER",
        "INSERT",
        "INTERSECT",
        "INTO",
        "IS",
        "JOIN",
        "KEY",
        "LEFT",
        "LIKE",
        "LIMIT",
        "NOT",
        "NOTHING",
        "NOWAIT",
        "NULL",
        "OFFSET",
        "ON",
        "OR",
        "ORDER",
        "OUTER",
        "PRIMARY",
        "RECURSIVE",
        "REFERENCES",
        "RESTRICT",
        "RETURNING",
        "REVOKE",
        "RIGHT",
        "ROLLBACK",
        "SCHEMA",
        "SELECT",
        "SET",
        "SHARE",
        "TABLE",
        "THEN",
        "TRANSACTION",
        "TRIGGER",
        "TRUE",
        "UNION",
        "UNIQUE",
        "UPDATE",
        "USING",
        "VACUUM",
        "VALUES",
        "VIEW",
        "WHEN",
        "WHERE",
        "WITH",
    }
)


# ---------------------------------------------------------------------------
# Core Identifier
# ---------------------------------------------------------------------------


class Identifier:
    """Validated, quoted, immutable SQL identifier.

    Created once, validated once, safe to interpolate into SQL forever.
    ``__str__`` returns the dialect-quoted form so
    ``f"SELECT * FROM {table}"`` is always safe when *table* is an
    ``Identifier``.

    Args:
        name: The raw identifier name.
        dialect: Target SQL dialect for quoting.  Defaults to PostgreSQL.

    Raises:
        InvalidIdentifierError: If the name is empty, contains invalid
            characters, or exceeds the dialect's maximum length.
    """

    __slots__ = ("_dialect", "_name", "_quoted")

    def __init__(
        self,
        name: str,
        *,
        dialect: SQLDialect = SQLDialect.POSTGRESQL,
    ) -> None:
        if not name:
            raise InvalidIdentifierError(
                "SQL identifier cannot be empty",
                identifier=name,
            )
        if not _IDENT_RE.match(name):
            raise InvalidIdentifierError(
                f"Invalid SQL identifier: {name!r}. "
                "Must match pattern [a-zA-Z_][a-zA-Z0-9_]*",
                identifier=name,
            )
        max_len = MAX_IDENTIFIER_LENGTHS.get(dialect, DEFAULT_MAX_IDENTIFIER_LENGTH)
        if len(name) > max_len:
            raise InvalidIdentifierError(
                f"SQL identifier {name!r} exceeds maximum length "
                f"of {max_len} for dialect {dialect.value}",
                identifier=name,
            )
        self._name: str = name
        self._dialect: SQLDialect = dialect
        self._quoted: str = self._quote(name, dialect)

    @staticmethod
    def _quote(name: str, dialect: SQLDialect) -> str:
        """Return the dialect-appropriate quoted identifier."""
        if dialect == SQLDialect.MYSQL:
            return f"`{name}`"
        return f'"{name}"'

    @property
    def name(self) -> str:
        """The raw, unquoted identifier name."""
        return self._name

    @property
    def quoted(self) -> str:
        """The dialect-quoted identifier, safe for SQL interpolation."""
        return self._quoted

    @property
    def dialect(self) -> SQLDialect:
        """The SQL dialect this identifier is quoted for."""
        return self._dialect

    @property
    def is_reserved(self) -> bool:
        """Whether this identifier is a SQL reserved word."""
        return self._name.upper() in _RESERVED_WORDS

    def __str__(self) -> str:
        """Return the quoted identifier (safe for SQL interpolation)."""
        return self._quoted

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Identifier):
            return (
                self._name == other._name
                and self._dialect == other._dialect
                and type(self) is type(other)
            )
        return NotImplemented

    def __hash__(self) -> int:
        return hash((type(self).__name__, self._name, self._dialect))


# ---------------------------------------------------------------------------
# Concrete identifier types
# ---------------------------------------------------------------------------


class Table(Identifier):
    """A validated SQL table name.

    Example::

        t = Table("users")
        query = f"SELECT * FROM {t}"  # SELECT * FROM "users"
    """


class Column(Identifier):
    """A validated SQL column name.

    Example::

        c = Column("email")
        query = f"SELECT {c} FROM users"  # SELECT "email" FROM users
    """


class Schema(Identifier):
    """A validated SQL schema name."""


# ---------------------------------------------------------------------------
# Composite types
# ---------------------------------------------------------------------------


class QualifiedTable:
    """A schema-qualified table name: ``schema.table``.

    Example::

        qt = QualifiedTable(Schema("public"), Table("users"))
        query = f"SELECT * FROM {qt}"  # SELECT * FROM "public"."users"
    """

    __slots__ = ("_schema", "_table")

    def __init__(self, schema: Schema, table: Table) -> None:
        self._schema = schema
        self._table = table

    @property
    def schema(self) -> Schema:
        """The schema component."""
        return self._schema

    @property
    def table(self) -> Table:
        """The table component."""
        return self._table

    @property
    def quoted(self) -> str:
        """The fully-qualified, quoted identifier."""
        return f"{self._schema.quoted}.{self._table.quoted}"

    def __str__(self) -> str:
        return self.quoted

    def __repr__(self) -> str:
        return f"QualifiedTable({self._schema!r}, {self._table!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, QualifiedTable):
            return self._schema == other._schema and self._table == other._table
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self._schema, self._table))


# ---------------------------------------------------------------------------
# Cached factory functions
# ---------------------------------------------------------------------------


@lru_cache(maxsize=512)
def table(name: str, *, dialect: SQLDialect = SQLDialect.POSTGRESQL) -> Table:
    """Create a cached, validated :class:`Table` identifier.

    Repeated calls with the same arguments return the **same object**.

    Args:
        name: Raw table name.
        dialect: SQL dialect for quoting.

    Returns:
        A validated, dialect-quoted :class:`Table` identifier.
    """
    return Table(name, dialect=dialect)


@lru_cache(maxsize=1024)
def column(name: str, *, dialect: SQLDialect = SQLDialect.POSTGRESQL) -> Column:
    """Create a cached, validated :class:`Column` identifier.

    Args:
        name: Raw column name.
        dialect: SQL dialect for quoting.

    Returns:
        A validated, dialect-quoted :class:`Column` identifier.
    """
    return Column(name, dialect=dialect)


@lru_cache(maxsize=64)
def schema(name: str, *, dialect: SQLDialect = SQLDialect.POSTGRESQL) -> Schema:
    """Create a cached, validated :class:`Schema` identifier.

    Args:
        name: Raw schema name.
        dialect: SQL dialect for quoting.

    Returns:
        A validated, dialect-quoted :class:`Schema` identifier.
    """
    return Schema(name, dialect=dialect)


def validate_identifier(
    name: str, *, dialect: SQLDialect = SQLDialect.POSTGRESQL
) -> str:
    """Validate *name* as a safe SQL identifier and return it.

    Fail-closed guard for call sites that interpolate identifiers into raw
    DDL/DML strings. Raises :class:`InvalidIdentifierError` on empty names,
    invalid characters, or dialect length overflow.

    Args:
        name: The identifier to validate.
        dialect: SQL dialect for length limits (default PostgreSQL).

    Returns:
        The validated name, unchanged.

    Raises:
        InvalidIdentifierError: On any validation failure.
    """
    Identifier(name=name, dialect=dialect)
    return name


__all__ = [
    "DEFAULT_MAX_IDENTIFIER_LENGTH",
    "MAX_IDENTIFIER_LENGTHS",
    "Column",
    "Identifier",
    "QualifiedTable",
    "Schema",
    "Table",
    "column",
    "schema",
    "table",
    "validate_identifier",
]
