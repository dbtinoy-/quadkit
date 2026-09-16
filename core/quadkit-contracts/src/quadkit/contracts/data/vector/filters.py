"""Vendor-neutral metadata filter primitives for vector search."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from quadkit.contracts.data.types import LogicalOperator


class FilterOperator(StrEnum):
    """Comparison operators for metadata filtering."""

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


@dataclass(frozen=True, slots=True)
class MetadataCondition:
    """A single metadata filter condition."""

    field: str
    operator: FilterOperator
    value: Any


@dataclass(frozen=True, slots=True)
class MetadataConditionGroup:
    """A group of conditions combined with AND/OR."""

    logical_operator: LogicalOperator
    conditions: tuple[MetadataCondition | MetadataConditionGroup, ...]


# Union type for protocol signatures
MetadataFilter = MetadataCondition | MetadataConditionGroup


class Filter:
    """Static factory for building metadata filters.

    Usage:
        ```python
        f = Filter.and_(
            Filter.eq("category", "science"),
            Filter.gte("year", 2020),
            Filter.or_(
                Filter.eq("status", "published"),
                Filter.eq("status", "preprint"),
            ),
        )
        ```
    """

    @staticmethod
    def eq(field_name: str, value: Any) -> MetadataCondition:
        """Equality: field == value."""
        return MetadataCondition(field_name, FilterOperator.EQ, value)

    @staticmethod
    def ne(field_name: str, value: Any) -> MetadataCondition:
        """Not equal: field != value."""
        return MetadataCondition(field_name, FilterOperator.NE, value)

    @staticmethod
    def gt(field_name: str, value: Any) -> MetadataCondition:
        """Greater than: field > value."""
        return MetadataCondition(field_name, FilterOperator.GT, value)

    @staticmethod
    def gte(field_name: str, value: Any) -> MetadataCondition:
        """Greater than or equal: field >= value."""
        return MetadataCondition(field_name, FilterOperator.GTE, value)

    @staticmethod
    def lt(field_name: str, value: Any) -> MetadataCondition:
        """Less than: field < value."""
        return MetadataCondition(field_name, FilterOperator.LT, value)

    @staticmethod
    def lte(field_name: str, value: Any) -> MetadataCondition:
        """Less than or equal: field <= value."""
        return MetadataCondition(field_name, FilterOperator.LTE, value)

    @staticmethod
    def in_(field_name: str, values: list[Any]) -> MetadataCondition:
        """Membership: field in values."""
        return MetadataCondition(field_name, FilterOperator.IN, values)

    @staticmethod
    def not_in(field_name: str, values: list[Any]) -> MetadataCondition:
        """Exclusion: field not in values."""
        return MetadataCondition(field_name, FilterOperator.NOT_IN, values)

    @staticmethod
    def exists(field_name: str, should_exist: bool = True) -> MetadataCondition:
        """Field existence: field exists (or not)."""
        return MetadataCondition(field_name, FilterOperator.EXISTS, should_exist)

    @staticmethod
    def contains(field_name: str, value: str) -> MetadataCondition:
        """String containment: value in field."""
        return MetadataCondition(field_name, FilterOperator.CONTAINS, value)

    @staticmethod
    def and_(*conditions: MetadataFilter) -> MetadataConditionGroup:
        """Logical AND of conditions."""
        return MetadataConditionGroup(LogicalOperator.AND, tuple(conditions))

    @staticmethod
    def or_(*conditions: MetadataFilter) -> MetadataConditionGroup:
        """Logical OR of conditions."""
        return MetadataConditionGroup(LogicalOperator.OR, tuple(conditions))


__all__ = [
    "Filter",
    "FilterOperator",
    "LogicalOperator",
    "MetadataCondition",
    "MetadataConditionGroup",
    "MetadataFilter",
]
