"""Typed SQL filter value objects."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from quadkit.contracts.data.identifiers import Column


def _resolve_field_name(reference: Any) -> str:
    """Resolve a field reference to a SQL column name."""
    if isinstance(reference, str) and reference:
        return reference

    for attr in ("name", "field_name", "alias", "key", "__name__"):
        value = getattr(reference, attr, None)
        if isinstance(value, str) and value:
            return value

    msg = f"Cannot resolve SQL field name from {reference!r}"
    raise TypeError(msg)


@dataclass(frozen=True)
class Filter:
    """Composable SQL filter expression."""

    kind: str
    field_name: str | None = None
    operator: str | None = None
    value: Any = None
    children: tuple[Filter, ...] = ()

    def __and__(self, other: Filter) -> Filter:
        """Combine two filters with ``AND``."""
        return Filter(kind="and", children=(self, ensure_filter(other)))

    def __or__(self, other: Filter) -> Filter:
        """Combine two filters with ``OR``."""
        return Filter(kind="or", children=(self, ensure_filter(other)))

    def __invert__(self) -> Filter:
        """Negate a filter with ``NOT``."""
        return Filter(kind="not", children=(self,))

    def to_sql(self) -> tuple[str, list[Any]]:
        """Render the filter expression to SQL and parameters."""
        if self.kind == "raw":
            sql, raw_params = self.value
            return f"({sql})", list(raw_params)

        if self.kind in {"and", "or"}:
            connector = " AND " if self.kind == "and" else " OR "
            rendered = [child.to_sql() for child in self.children]
            sql = connector.join(part for part, _ in rendered)
            params = [param for _, child_params in rendered for param in child_params]
            return f"({sql})", params

        if self.kind == "not":
            sql, params = self.children[0].to_sql()
            return f"NOT ({sql})", params

        if self.field_name is None or self.operator is None:
            raise ValueError("Predicate filters require field_name and operator")

        field = str(Column(self.field_name))
        operator = self.operator
        value = self.value

        if operator == "eq":
            if value is None:
                return f"{field} IS NULL", []
            return f"{field} = ?", [value]

        if operator == "ne":
            if value is None:
                return f"{field} IS NOT NULL", []
            return f"{field} != ?", [value]

        if operator == "gt":
            return f"{field} > ?", [value]

        if operator == "gte":
            return f"{field} >= ?", [value]

        if operator == "lt":
            return f"{field} < ?", [value]

        if operator == "lte":
            return f"{field} <= ?", [value]

        if operator == "in":
            values = list(value)
            if not values:
                return "1 = 0", []
            placeholders = ", ".join("?" for _ in values)
            return f"{field} IN ({placeholders})", values

        if operator == "not_in":
            values = list(value)
            if not values:
                return "1 = 1", []
            placeholders = ", ".join("?" for _ in values)
            return f"{field} NOT IN ({placeholders})", values

        if operator == "like":
            return f"{field} LIKE ?", [value]

        if operator == "ilike":
            # `ILIKE` is Postgres-only syntax: SQLite rejects it outright
            # (`near "ILIKE": syntax error`) and MySQL has no equivalent.
            # `LOWER(x) LIKE LOWER(?)` is the same predicate in every dialect
            # the framework supports, so the filter means what it says on all
            # three instead of working only where it was first written.
            return f"LOWER({field}) LIKE LOWER(?)", [value]

        if operator == "between":
            low, high = value
            return f"{field} BETWEEN ? AND ?", [low, high]

        if operator == "is_null":
            return f"{field} IS NULL", []

        if operator == "is_not_null":
            return f"{field} IS NOT NULL", []

        msg = f"Unsupported filter operator: {operator}"
        raise ValueError(msg)


class F:
    """Field reference used to build typed repository filters."""

    __slots__ = ("field_name",)
    __hash__ = object.__hash__

    def __init__(self, reference: Any) -> None:
        self.field_name = _resolve_field_name(reference)

    def __eq__(self, value: object) -> Filter:  # type: ignore[override]
        """Create an equality filter."""
        return self._predicate("eq", value)

    def __ne__(self, value: object) -> Filter:  # type: ignore[override]
        """Create an inequality filter."""
        return self._predicate("ne", value)

    def __gt__(self, value: Any) -> Filter:
        """Create a greater-than filter."""
        return self._predicate("gt", value)

    def __ge__(self, value: Any) -> Filter:
        """Create a greater-than-or-equal filter."""
        return self._predicate("gte", value)

    def __lt__(self, value: Any) -> Filter:
        """Create a less-than filter."""
        return self._predicate("lt", value)

    def __le__(self, value: Any) -> Filter:
        """Create a less-than-or-equal filter."""
        return self._predicate("lte", value)

    def in_(self, values: Iterable[Any]) -> Filter:
        """Create an ``IN`` filter."""
        return self._predicate("in", list(values))

    def not_in(self, values: Iterable[Any]) -> Filter:
        """Create a ``NOT IN`` filter."""
        return self._predicate("not_in", list(values))

    def like(self, pattern: str) -> Filter:
        """Create a ``LIKE`` filter."""
        return self._predicate("like", pattern)

    def ilike(self, pattern: str) -> Filter:
        """Create a case-insensitive ``LIKE`` filter (portable across dialects)."""
        return self._predicate("ilike", pattern)

    def contains(self, value: Any) -> Filter:
        """Create a containment filter using wildcard matching."""
        return self.like(f"%{value}%")

    def is_null(self) -> Filter:
        """Create an ``IS NULL`` filter."""
        return self._predicate("is_null", None)

    def is_not_null(self) -> Filter:
        """Create an ``IS NOT NULL`` filter."""
        return self._predicate("is_not_null", None)

    def between(self, low: Any, high: Any) -> Filter:
        """Create a ``BETWEEN`` filter."""
        return self._predicate("between", (low, high))

    def _predicate(self, operator: str, value: Any) -> Filter:
        return Filter(
            kind="predicate",
            field_name=self.field_name,
            operator=operator,
            value=value,
        )


def raw_predicate(sql: str, *params: Any) -> Filter:
    """Build a filter from a parameterized SQL predicate.

    Some conditions are not expressible as column-operator-value — a code is
    "exhausted" when ``COALESCE(used_count, 0) >= COALESCE(max_uses, 1)``, an
    expression on two columns with nullable defaults. Without an escape hatch
    the caller has to abandon the filter builder (and therefore ``find_many``,
    ``count`` and ``delete_where``) for a hand-written statement, which is how
    one such rule ends up re-implemented three times and drifted.

    The predicate is inserted verbatim, so it must not interpolate user input:
    values belong in *params*, which the caller's parameters are extended
    with. Everything else — AND/OR composition, parameter order, the RLS hook,
    the dialect's placeholders — stays the framework's job.

    Args:
        sql: A SQL boolean expression using ``?`` placeholders.
        *params: Values for those placeholders.

    Returns:
        A ``Filter`` that composes with ``&``, ``|`` and ``~``.

    Example:
        >>> (F("status") == "active") & raw_predicate("COALESCE(n, 0) > ?", 0)
    """
    return Filter(kind="raw", value=(sql, list(params)))


class ComputedKey:
    """A ``GROUP BY`` key that is an expression rather than a column.

    ``aggregate`` takes column names, so a dashboard that groups on a computed
    value — an hour-floored timestamp, a calendar day — could not use it and
    hand-wrote the statement instead. The two hooks below are all ``aggregate``
    needs: :meth:`to_select` for the projected, aliased form and :meth:`to_sql`
    for the grouping form. They must render the *same* expression, because some
    dialects reject a projection that is not also grouped.
    """

    def to_sql(self) -> str:
        """Render the expression without its alias."""
        raise NotImplementedError

    def to_select(self) -> str:
        """Render the expression as a projected, aliased column."""
        raise NotImplementedError


@dataclass(frozen=True)
class Bucket(ComputedKey):
    """A computed ``GROUP BY`` key: one column floored to a multiple of *size*.

    Dashboards group timestamps into buckets — "one point per hour", "one point
    per day" — and that is an *expression*, not a column: upstream's rollup
    floors each second with ``created_at - created_at % 3600``. ``aggregate``
    takes column names, so without this a caller has to abandon the repository
    and hand-write the statement, which is how the same bucketing rule ends up
    re-implemented (and drifted) in every module that charts.

    Both halves are validated: the column and the alias through ``Column``, the
    size through the constructor. The rendered form is

        ("start_time" - ("start_time" % 3600)) AS "created_at"

    which SQLite, PostgreSQL and MySQL all evaluate identically for the
    non-negative integers a unix timestamp is.

    Example:
        >>> await repo.aggregate(
        ...     count="*", sum="quota", group_by="model", bucket=Bucket("start_time", 3600, "created_at")
        ... )
    """

    field_name: Any
    size: int
    alias: str

    def __post_init__(self) -> None:
        """Resolve and validate the column, the size and the alias."""
        if (
            isinstance(self.size, bool)
            or not isinstance(self.size, int)
            or self.size <= 0
        ):
            msg = f"Bucket size must be a positive integer, got {self.size!r}"
            raise ValueError(msg)
        object.__setattr__(self, "field_name", _resolve_field_name(self.field_name))
        Column(self.field_name)
        Column(self.alias)

    def to_sql(self) -> str:
        """Render the bucketed expression, without its alias."""
        column = Column(self.field_name)
        return f"({column} - ({column} % {int(self.size)}))"

    def to_select(self) -> str:
        """Render the expression as a projected, aliased column."""
        return f"{self.to_sql()} AS {Column(self.alias)}"


@dataclass(frozen=True)
class DateBucket(ComputedKey):
    """A computed ``GROUP BY`` key: the calendar date of a timestamp column.

    "Sign-ups per day" is a projection of ``DATE(created_at)``, which is an
    expression, so ``aggregate`` — whose ``group_by`` takes column names —
    could not express it, and the caller either hand-wrote the statement or
    fetched every row and counted in Python: a table scan to draw one line.
    The rendered form is

        DATE("created_at") AS "day"

    which SQLite, PostgreSQL and MySQL all accept (Postgres exposes ``date()``
    as a cast function). Day granularity is the portable subset; month and year
    groupings differ per dialect and are better served by flooring an epoch
    column with :class:`Bucket`.

    Example:
        >>> await repo.aggregate(count="*", bucket=DateBucket("created_at", "day"))
    """

    field_name: Any
    alias: str

    def __post_init__(self) -> None:
        """Resolve and validate the column and the alias."""
        object.__setattr__(self, "field_name", _resolve_field_name(self.field_name))
        Column(self.field_name)
        Column(self.alias)

    def to_sql(self) -> str:
        """Render ``DATE(<column>)``, without its alias."""
        return f"DATE({Column(self.field_name)})"

    def to_select(self) -> str:
        """Render the date expression as a projected, aliased column."""
        return f"{self.to_sql()} AS {Column(self.alias)}"


def field(reference: Any) -> F:
    """Create an ``F`` builder from a field reference."""
    return F(reference)


def ensure_filter(value: Any) -> Filter:
    """Ensure a value is a typed SQL filter."""
    if isinstance(value, Filter):
        return value
    msg = f"Expected Filter, got {type(value).__name__}"
    raise TypeError(msg)


def normalize_filters(values: Iterable[Any]) -> list[Filter]:
    """Normalize an iterable of filter inputs to ``Filter`` instances."""
    normalized: list[Filter] = []
    for value in values:
        normalized.append(ensure_filter(value))
    return normalized


__all__ = [
    "Bucket",
    "ComputedKey",
    "DateBucket",
    "F",
    "Filter",
    "ensure_filter",
    "field",
    "normalize_filters",
    "raw_predicate",
]
