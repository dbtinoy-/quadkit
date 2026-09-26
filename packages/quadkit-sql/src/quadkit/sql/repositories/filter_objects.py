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
            return f"{field} ILIKE ?", [value]

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
        """Create an ``ILIKE`` filter."""
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


__all__ = ["F", "Filter", "ensure_filter", "field", "normalize_filters"]
