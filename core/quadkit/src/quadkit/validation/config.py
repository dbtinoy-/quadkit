"""Configuration for the validation subsystem.

Contains :class:`ValidationConfig`, which controls strictness and
error accumulation behaviour of the :class:`~quadkit.validation.validator.ValidatorImpl`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationConfig:
    """Validation pipeline configuration."""

    strict: bool = False  # consumed by: ValidatorImpl strict mode — forward
    stop_on_first_error: bool = (
        False  # consumed by: ValidatorImpl error accumulation — forward
    )
    coerce_types: bool = False  # consumed by: ValidatorImpl type coercion — forward


__all__ = ["ValidationConfig"]
