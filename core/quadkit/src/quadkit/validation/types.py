"""Type definitions for the validation subsystem.

TypeVars and aliases unique to the validation package.
``RuleResult`` and ``ValidationResult`` are canonical in
``quadkit.contracts.core.validation`` and re-exported from there.
"""

from __future__ import annotations

from typing import TypeAlias, TypeVar

from quadkit.contracts.core.validation import RuleResult, ValidationResult
from quadkit.contracts.exceptions.domain import FieldError, ValidationError

T = TypeVar("T")  # Validated output type

FieldName: TypeAlias = str

__all__ = [
    "FieldError",
    "FieldName",
    "RuleResult",
    "T",
    "ValidationError",
    "ValidationResult",
]
