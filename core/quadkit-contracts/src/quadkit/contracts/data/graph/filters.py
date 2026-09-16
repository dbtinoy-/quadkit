"""Property filter primitives for graph nodes and edges."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from quadkit.contracts.data.types import LogicalOperator


class PropertyOperator(StrEnum):
    """Comparison operators for property filtering."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    EXISTS = "exists"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"


@dataclass(frozen=True, slots=True)
class PropertyCondition:
    """A single property filter condition."""

    field: str
    operator: PropertyOperator
    value: Any


@dataclass(frozen=True, slots=True)
class PropertyConditionGroup:
    """A group of conditions combined with AND/OR."""

    logical_operator: LogicalOperator
    conditions: tuple[PropertyCondition | PropertyConditionGroup, ...]


PropertyFilter = PropertyCondition | PropertyConditionGroup


class Prop:
    """Static factory for building property filters.

    Usage:
        ```python
        f = Prop.and_(
            Prop.eq("active", True),
            Prop.gte("age", 21),
            Prop.or_(
                Prop.eq("role", "admin"),
                Prop.eq("role", "moderator"),
            ),
        )
        ```
    """

    @staticmethod
    def eq(field: str, value: Any) -> PropertyCondition:
        """Equality: field == value."""
        return PropertyCondition(field, PropertyOperator.EQ, value)

    @staticmethod
    def ne(field: str, value: Any) -> PropertyCondition:
        """Not equal: field != value."""
        return PropertyCondition(field, PropertyOperator.NE, value)

    @staticmethod
    def gt(field: str, value: Any) -> PropertyCondition:
        """Greater than: field > value."""
        return PropertyCondition(field, PropertyOperator.GT, value)

    @staticmethod
    def gte(field: str, value: Any) -> PropertyCondition:
        """Greater than or equal: field >= value."""
        return PropertyCondition(field, PropertyOperator.GTE, value)

    @staticmethod
    def lt(field: str, value: Any) -> PropertyCondition:
        """Less than: field < value."""
        return PropertyCondition(field, PropertyOperator.LT, value)

    @staticmethod
    def lte(field: str, value: Any) -> PropertyCondition:
        """Less than or equal: field <= value."""
        return PropertyCondition(field, PropertyOperator.LTE, value)

    @staticmethod
    def in_(field: str, values: list[Any]) -> PropertyCondition:
        """Membership: field in values."""
        return PropertyCondition(field, PropertyOperator.IN, values)

    @staticmethod
    def not_in(field: str, values: list[Any]) -> PropertyCondition:
        """Exclusion: field not in values."""
        return PropertyCondition(field, PropertyOperator.NOT_IN, values)

    @staticmethod
    def exists(field: str, should_exist: bool = True) -> PropertyCondition:
        """Field existence check."""
        return PropertyCondition(field, PropertyOperator.EXISTS, should_exist)

    @staticmethod
    def contains(field: str, value: str) -> PropertyCondition:
        """String containment: value in field."""
        return PropertyCondition(field, PropertyOperator.CONTAINS, value)

    @staticmethod
    def starts_with(field: str, value: str) -> PropertyCondition:
        """String prefix match."""
        return PropertyCondition(field, PropertyOperator.STARTS_WITH, value)

    @staticmethod
    def ends_with(field: str, value: str) -> PropertyCondition:
        """String suffix match."""
        return PropertyCondition(field, PropertyOperator.ENDS_WITH, value)

    @staticmethod
    def regex(field: str, pattern: str) -> PropertyCondition:
        """Regular expression match."""
        return PropertyCondition(field, PropertyOperator.REGEX, pattern)

    @staticmethod
    def and_(*conditions: PropertyFilter) -> PropertyConditionGroup:
        """Logical AND of conditions."""
        return PropertyConditionGroup(LogicalOperator.AND, tuple(conditions))

    @staticmethod
    def or_(*conditions: PropertyFilter) -> PropertyConditionGroup:
        """Logical OR of conditions."""
        return PropertyConditionGroup(LogicalOperator.OR, tuple(conditions))


__all__ = [
    "Prop",
    "PropertyCondition",
    "PropertyConditionGroup",
    "PropertyFilter",
    "PropertyOperator",
]
