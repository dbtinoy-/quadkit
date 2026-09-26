"""Value Object base class for immutable domain concepts.

Value objects are immutable objects that represent descriptive aspects
of the domain with no conceptual identity.
"""

from __future__ import annotations

from abc import ABC
from typing import Any

from quadkit.domain import ValueObject as BaseValueObject


class ValueObject(BaseValueObject, ABC):
    """Base class for value objects.

    Value objects:
    - Are immutable (frozen=True)
    - Have no identity
    - Are compared by value (all fields)
    - Can be freely shared
    """

    model_config = {  # noqa: RUF012
        "frozen": True,  # Immutable
        "arbitrary_types_allowed": True,
    }


class SingleValueObject(ValueObject):
    """Value object that wraps a single value.

    Useful for strongly-typed primitives.

    Example:
        ```python
        class OrderId(SingleValueObject[UUID]):
            value: UUID

        class Email(SingleValueObject[str]):
            value: str

            @field_validator('value')
            def validate_email(cls, v):
                if '@' not in v:
                    raise ValueError('Invalid email')
                return v
        ```
    """

    value: Any

    def __str__(self) -> str:
        """String representation returns the value."""
        return str(self.value)


__all__ = ["SingleValueObject", "ValueObject"]
