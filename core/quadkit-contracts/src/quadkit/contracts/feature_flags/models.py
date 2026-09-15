"""Feature flag value models for the Quadkit Framework.

Defines the data types used when evaluating feature flags, including
the flag type enum, value type alias, and full evaluation result.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class FlagType(StrEnum):
    """The evaluation strategy of a feature flag."""

    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    USER_ATTRIBUTE = "user_attribute"
    TIME_BASED = "time_based"
    VARIANT = "variant"


# Type alias for the value returned by flag evaluation.
# Simple flags → bool; percentage/variant flags → str | bool | float.
FlagValue = bool | str | float


@dataclass(frozen=True)
class FlagEvaluation:
    """The result of evaluating a single feature flag.

    Attributes:
        key: The flag identifier.
        value: The evaluated value (type depends on FlagType).
        flag_type: The type of flag evaluated.
        reason: Machine-readable reason code (e.g. "DEFAULT", "TARGETING").
        variant: Variant key for VARIANT-type flags, None otherwise.
        metadata: Arbitrary evaluation metadata from the provider.
    """

    key: str
    value: FlagValue
    flag_type: FlagType = FlagType.BOOLEAN
    reason: str = "DEFAULT"
    variant: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "FlagEvaluation",
    "FlagType",
    "FlagValue",
]
