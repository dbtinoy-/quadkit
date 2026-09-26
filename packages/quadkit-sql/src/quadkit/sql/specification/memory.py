"""SpecificationProtocol pattern implementation for Quadkit Framework.

The SpecificationProtocol pattern provides a way to define complex business rules
and queries in a composable, reusable manner. It allows building complex
predicates from simple specifications using logical operators.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from functools import reduce
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class MemorySpecification(Generic[T]):
    """Abstract base class for in-memory specifications in quadkit-sql.

    Implements the ``SpecificationProtocol`` protocol from ``quadkit.contracts.domain``
    with convenience ``and_`` / ``or_`` / ``not_`` named methods alongside
    the operator overloads (``&``, ``|``, ``~``).
    """

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Check if a candidate satisfies this specification."""

    def and_(self, other: MemorySpecification[T]) -> AndMemorySpecification[T]:
        """Combine with another specification using AND."""
        return AndMemorySpecification(self, other)

    def or_(self, other: MemorySpecification[T]) -> OrMemorySpecification[T]:
        """Combine with another specification using OR."""
        return OrMemorySpecification(self, other)

    def not_(self) -> NotMemorySpecification[T]:
        """Negate this specification."""
        return NotMemorySpecification(self)

    def __and__(self, other: MemorySpecification[T]) -> AndMemorySpecification[T]:
        """AND operator overload."""
        return self.and_(other)

    def __or__(self, other: MemorySpecification[T]) -> OrMemorySpecification[T]:
        """OR operator overload."""
        return self.or_(other)

    def __invert__(self) -> NotMemorySpecification[T]:
        """NOT operator overload."""
        return self.not_()


class AndMemorySpecification(MemorySpecification[T]):
    """SpecificationProtocol that combines two specifications with AND logic."""

    def __init__(
        self, left: MemorySpecification[T], right: MemorySpecification[T]
    ) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(
            candidate,
        )

    def __repr__(self) -> str:
        return f"({self.left} AND {self.right})"


class OrMemorySpecification(MemorySpecification[T]):
    """SpecificationProtocol that combines two specifications with OR logic."""

    def __init__(
        self, left: MemorySpecification[T], right: MemorySpecification[T]
    ) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(
            candidate,
        )

    def __repr__(self) -> str:
        return f"({self.left} OR {self.right})"


class NotMemorySpecification(MemorySpecification[T]):
    """SpecificationProtocol that negates another specification."""

    def __init__(self, spec: MemorySpecification[T]) -> None:
        self.spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self.spec.is_satisfied_by(candidate)

    def __repr__(self) -> str:
        return f"(NOT {self.spec})"


class CompositeMemorySpecification(MemorySpecification[T]):
    """SpecificationProtocol that combines multiple specifications."""

    def __init__(self, *specs: MemorySpecification[T], operator: str = "AND") -> None:
        self.specs = specs
        self.operator = operator.upper()

    def is_satisfied_by(self, candidate: T) -> bool:
        if self.operator == "AND":
            return all(spec.is_satisfied_by(candidate) for spec in self.specs)
        if self.operator == "OR":
            return any(spec.is_satisfied_by(candidate) for spec in self.specs)
        msg = f"Unsupported operator: {self.operator}"
        raise ValueError(msg)


class FieldSpecification(MemorySpecification[T]):
    """SpecificationProtocol based on a field value."""

    def __init__(self, field: str, value: Any, operator: str = "eq") -> None:
        self.field = field
        self.value = value
        self.operator = operator.lower()

    def is_satisfied_by(self, candidate: T) -> bool:
        field_value = getattr(candidate, self.field, None)

        if self.operator == "eq":
            return bool(field_value == self.value)
        if self.operator == "ne":
            return bool(field_value != self.value)
        if self.operator == "gt":
            return bool(field_value > self.value)
        if self.operator == "gte":
            return bool(field_value >= self.value)
        if self.operator == "lt":
            return bool(field_value < self.value)
        if self.operator == "lte":
            return bool(field_value <= self.value)
        if self.operator == "in":
            return bool(field_value in self.value)
        if self.operator == "contains":
            return bool(self.value in field_value if field_value else False)
        if self.operator == "startswith":
            return bool(
                str(field_value).startswith(str(self.value)) if field_value else False,
            )
        if self.operator == "endswith":
            return bool(
                str(field_value).endswith(str(self.value)) if field_value else False,
            )
        msg = f"Unsupported operator: {self.operator}"
        raise ValueError(msg)


class CustomSpecification(MemorySpecification[T]):
    """SpecificationProtocol based on a custom predicate function."""

    def __init__(self, predicate: Callable[[T], bool]) -> None:
        self.predicate = predicate

    def is_satisfied_by(self, candidate: T) -> bool:
        return self.predicate(candidate)


class MemorySpecificationBuilder(Generic[T]):
    """Builder for creating complex specifications."""

    def __init__(self) -> None:
        self._specs: list[MemorySpecification[T]] = []
        self._operator = "AND"

    def where(self, spec: MemorySpecification[T]) -> MemorySpecificationBuilder[T]:
        """Add a specification to the builder."""
        self._specs.append(spec)
        return self

    def field(
        self,
        field: str,
        value: Any,
        operator: str = "eq",
    ) -> MemorySpecificationBuilder[T]:
        """Add a field-based specification."""
        spec: MemorySpecification[T] = FieldSpecification(field, value, operator)
        return self.where(spec)

    def custom(self, predicate: Callable[[T], bool]) -> MemorySpecificationBuilder[T]:
        """Add a custom specification."""
        spec = CustomSpecification(predicate)
        return self.where(spec)

    def and_operator(self) -> MemorySpecificationBuilder[T]:
        """Set the combination operator to AND."""
        self._operator = "AND"
        return self

    def or_operator(self) -> MemorySpecificationBuilder[T]:
        """Set the combination operator to OR."""
        self._operator = "OR"
        return self

    def build(self) -> MemorySpecification[T]:
        """Build the final specification."""
        if not self._specs:
            # Return a specification that always returns True
            return CustomSpecification(lambda *_: True)
        if len(self._specs) == 1:
            return self._specs[0]
        return CompositeMemorySpecification(*self._specs, operator=self._operator)


# Utility functions


def field_equals(field: str, value: Any) -> Callable[[], FieldSpecification]:
    """Create a field equality specification factory."""
    return lambda: FieldSpecification(field, value, "eq")


def field_greater_than(field: str, value: Any) -> Callable[[], FieldSpecification]:
    """Create a field greater than specification factory."""
    return lambda: FieldSpecification(field, value, "gt")


def field_contains(field: str, value: Any) -> Callable[[], FieldSpecification]:
    """Create a field contains specification factory."""
    return lambda: FieldSpecification(field, value, "contains")


def and_specs(*specs: MemorySpecification[T]) -> MemorySpecification[T]:
    """Combine specifications with AND."""
    return reduce(lambda acc, spec: acc.and_(spec), specs)


def or_specs(*specs: MemorySpecification[T]) -> MemorySpecification[T]:
    """Combine specifications with OR."""
    return reduce(lambda acc, spec: acc.or_(spec), specs)


def not_spec(spec: MemorySpecification[T]) -> MemorySpecification[T]:
    """Negate a specification."""
    return spec.not_()


def matches(field: str, value: Any) -> FieldSpecification[Any]:
    """Create a field equality specification."""
    return FieldSpecification(field, value, "eq")


# Type aliases for common use cases
StringSpecification = MemorySpecification[str]
IntSpecification = MemorySpecification[int]
BoolSpecification = MemorySpecification[bool]


__all__ = [
    "AndMemorySpecification",
    "BoolSpecification",
    "CompositeMemorySpecification",
    "CustomSpecification",
    "FieldSpecification",
    "IntSpecification",
    "MemorySpecification",
    "MemorySpecificationBuilder",
    "NotMemorySpecification",
    "OrMemorySpecification",
    "StringSpecification",
    "and_specs",
    "field_contains",
    "field_equals",
    "field_greater_than",
    "matches",
    "not_spec",
    "or_specs",
]
