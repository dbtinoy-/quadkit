"""Validation types and exceptions.

This module re-exports ``ValidationError`` from ``quadkit.contracts.exceptions.domain``
for convenience, and defines validation protocols and result type aliases.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeAlias, TypeVar

from quadkit.contracts.core.result import Result

# ValidationError is defined in exceptions.domain - re-exported here for convenience
from quadkit.contracts.exceptions.domain import FieldError, ValidationError

T_co = TypeVar("T_co", covariant=True)

RuleResult: TypeAlias = Result[Any, FieldError]
ValidationResult: TypeAlias = Result[dict[str, Any], ValidationError]


class RuleProtocol(Protocol[T_co]):  # type: ignore[misc]
    """Protocol for a single validation rule applied to one field."""

    def __call__(self, value: Any, field_name: str) -> Result[T_co, FieldError]:
        """Validate *value* for *field_name* and return a Result."""
        ...


class AsyncRuleProtocol(Protocol[T_co]):  # type: ignore[misc]
    """Protocol for a single async validation rule applied to one field."""

    async def __call__(self, value: Any, field_name: str) -> Result[T_co, FieldError]:
        """Asynchronously validate *value* for *field_name* and return a Result."""
        ...


class ValidatorProtocol(Protocol[T_co]):
    """Protocol for a full-document validator that returns a Result."""

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """Validate *data* and return a Result with the cleaned dict or error."""
        ...

    def validate_object(self, obj: Any) -> Result[Any, ValidationError]:
        """Validate *obj* by reading its attributes."""
        ...


__all__ = [
    "AsyncRuleProtocol",
    "FieldError",
    "RuleProtocol",
    "RuleResult",
    "ValidationError",
    "ValidationResult",
    "ValidatorProtocol",
]
