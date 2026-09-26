"""SpecificationProtocol pattern for composable query conditions.

The SpecificationProtocol pattern allows building complex, reusable query conditions
that can be combined with logical operators (&, |, ~).

Example:
    class ActiveUsers(SqlSpecification):
        def to_sql(self, dialect):
            return "is_active = ?", [True]

    class RecentUsers(SqlSpecification):
        def __init__(self, days: int = 30):
            self.days = days
        def to_sql(self, dialect):
            return "created_at > NOW() - INTERVAL ? DAY", [self.days]

    # Compose with operators:
    spec = ActiveUsers() & RecentUsers(7)
    users = await user_repo.find_by_spec(spec, limit=50)

    # Negate:
    spec = ~ActiveUsers()  # inactive users
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from quadkit.contracts.data import Column
from quadkit.sql.query.sql_builder import SQLDialect

T = TypeVar("T")
TKey = TypeVar("TKey")


class SqlSpecification(ABC, Generic[T, TKey]):
    """Abstract base class for SQL query specifications with primary key awareness.

    SQL specifications produce SQL WHERE clauses via ``to_sql()`` and support
    composable operators (&, |, ~). The extra ``TKey`` type parameter enables
    primary-key-aware query building.

    Note:
        This does NOT extend core's ``BaseSpecification`` because it needs the
        additional ``TKey`` generic parameter. However, any subclass that also
        implements ``is_satisfied_by`` will structurally satisfy the contracts
        ``SpecificationProtocol[T]`` protocol (duck typing).
    """

    @abstractmethod
    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        """Convert this specification to a SQL WHERE clause fragment.

        Args:
            dialect: The SQL dialect to generate for.

        Returns:
            Tuple of (sql_fragment, params).
        """

    def __and__(self, other: SqlSpecification) -> AndSqlSpecification:
        """Combine with AND: spec1 & spec2."""
        return AndSqlSpecification(self, other)

    def __or__(self, other: SqlSpecification) -> OrSqlSpecification:
        """Combine with OR: spec1 | spec2."""
        return OrSqlSpecification(self, other)

    def __invert__(self) -> NotSqlSpecification:
        """Negate: ~spec."""
        return NotSqlSpecification(self)


class AndSqlSpecification(SqlSpecification):
    """Combines two specifications with AND logic."""

    def __init__(self, left: SqlSpecification, right: SqlSpecification) -> None:
        self.left = left
        self.right = right

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        left_sql, left_params = self.left.to_sql(dialect)
        right_sql, right_params = self.right.to_sql(dialect)
        return f"({left_sql}) AND ({right_sql})", [*left_params, *right_params]


class OrSqlSpecification(SqlSpecification):
    """Combines two specifications with OR logic."""

    def __init__(self, left: SqlSpecification, right: SqlSpecification) -> None:
        self.left = left
        self.right = right

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        left_sql, left_params = self.left.to_sql(dialect)
        right_sql, right_params = self.right.to_sql(dialect)
        return f"({left_sql}) OR ({right_sql})", [*left_params, *right_params]


class NotSqlSpecification(SqlSpecification):
    """Negates a specification."""

    def __init__(self, spec: SqlSpecification) -> None:
        self.spec = spec

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        sql, params = self.spec.to_sql(dialect)
        return f"NOT ({sql})", params


# ---------------------------------------------------------------------------
# Common built-in specifications
# ---------------------------------------------------------------------------


class FieldEquals(SqlSpecification):
    """Matches when field equals value."""

    def __init__(self, field: str, value: Any) -> None:
        self.field = str(Column(field))
        self.value = value

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return f"{self.field} = ?", [self.value]


class FieldIn(SqlSpecification):
    """Matches when field is in a set of values."""

    def __init__(self, field: str, values: list[Any]) -> None:
        self.field = str(Column(field))
        self.values = values

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        if not self.values:
            return "1=0", []
        placeholders = ", ".join("?" for _ in self.values)
        return f"{self.field} IN ({placeholders})", list(self.values)


class FieldBetween(SqlSpecification):
    """Matches when field is between low and high."""

    def __init__(self, field: str, low: Any, high: Any) -> None:
        self.field = str(Column(field))
        self.low = low
        self.high = high

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return f"{self.field} BETWEEN ? AND ?", [self.low, self.high]


class FieldLike(SqlSpecification):
    """Matches when field matches a LIKE pattern."""

    def __init__(self, field: str, pattern: str) -> None:
        self.field = str(Column(field))
        self.pattern = pattern

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return f"{self.field} LIKE ?", [self.pattern]


class FieldIsNull(SqlSpecification):
    """Matches when field is NULL."""

    def __init__(self, field: str) -> None:
        self.field = str(Column(field))

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return f"{self.field} IS NULL", []


class FieldIsNotNull(SqlSpecification):
    """Matches when field is NOT NULL."""

    def __init__(self, field: str) -> None:
        self.field = str(Column(field))

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return f"{self.field} IS NOT NULL", []


class FieldGreaterThan(SqlSpecification):
    """Matches when field > value."""

    def __init__(self, field: str, value: Any) -> None:
        self.field = str(Column(field))
        self.value = value

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return f"{self.field} > ?", [self.value]


class FieldLessThan(SqlSpecification):
    """Matches when field < value."""

    def __init__(self, field: str, value: Any) -> None:
        self.field = str(Column(field))
        self.value = value

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return f"{self.field} < ?", [self.value]


class RawSpecification(SqlSpecification):
    """A raw SQL specification for cases not covered by built-in specs.

    Note:
        Escape hatch: the SQL fragment is passed through verbatim. Callers
        must never interpolate user input into ``sql`` — always use ``?``
        placeholders with ``params``.
    """

    def __init__(self, sql: str, params: list[Any] | None = None) -> None:
        self._sql = sql
        self._params = params or []

    def to_sql(
        self, dialect: SQLDialect = SQLDialect.POSTGRESQL
    ) -> tuple[str, list[Any]]:
        return self._sql, self._params


def and_specs(*specs: SqlSpecification) -> SqlSpecification:
    """Combine specifications with AND."""
    from functools import reduce

    return reduce(lambda acc, spec: acc & spec, specs)


def or_specs(*specs: SqlSpecification) -> SqlSpecification:
    """Combine specifications with OR."""
    from functools import reduce

    return reduce(lambda acc, spec: acc | spec, specs)


def not_spec(spec: SqlSpecification) -> SqlSpecification:
    """Negate a specification."""
    return ~spec


__all__ = [
    "AndSqlSpecification",
    "FieldBetween",
    "FieldEquals",
    "FieldGreaterThan",
    "FieldIn",
    "FieldIsNotNull",
    "FieldIsNull",
    "FieldLessThan",
    "FieldLike",
    "NotSqlSpecification",
    "OrSqlSpecification",
    "RawSpecification",
    "SqlSpecification",
    "and_specs",
    "not_spec",
    "or_specs",
]
