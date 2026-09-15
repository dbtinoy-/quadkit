"""Validator collection utilities for domain models.

This module provides functions for scanning class hierarchies and collecting
validators decorated with @field_validator and @model_validator.
"""

from __future__ import annotations

from typing import Any


def collect_field_validators(cls: type) -> dict[str, list[tuple[str, Any]]]:
    """Scan MRO for methods decorated with ``@field_validator``.

    Returns a dict keyed by field name -> list of ``(mode, callable)`` tuples,
    sorted so ``"before"`` validators run before ``"after"`` validators.

    Args:
        cls: The class to scan for field validators.

    Returns:
        A dictionary mapping field names to lists of (mode, validator) tuples.
    """
    validators: dict[str, list[tuple[str, Any]]] = {}
    seen: set[str] = set()
    for klass in reversed(cls.__mro__):
        for attr_name, attr_val in vars(klass).items():
            if attr_name in seen:
                continue
            # classmethod wraps the real function; unwrap all layers
            func = attr_val
            while isinstance(func, classmethod):
                func = func.__func__
            if not getattr(func, "_field_validator", False):
                continue
            seen.add(attr_name)
            mode = getattr(func, "_validator_mode", "before")
            for field_name in getattr(func, "_validator_fields", ()):
                validators.setdefault(field_name, []).append((mode, func))
    # Sort: "before" first, "after" second
    for entries in validators.values():
        entries.sort(key=lambda t: 0 if t[0] == "before" else 1)
    return validators


def collect_model_validators(cls: type) -> dict[str, list[Any]]:
    """Scan MRO for methods decorated with ``@model_validator``.

    Returns a dict keyed by mode (``"before"`` / ``"after"`` / ``"wrap"``)
    -> list of callables.

    Args:
        cls: The class to scan for model validators.

    Returns:
        A dictionary mapping validator modes to lists of validator functions.
    """
    validators: dict[str, list[Any]] = {"before": [], "after": [], "wrap": []}
    seen: set[str] = set()
    for klass in reversed(cls.__mro__):
        for attr_name, attr_val in vars(klass).items():
            if attr_name in seen:
                continue
            func = attr_val
            while isinstance(func, classmethod):
                func = func.__func__
            if not getattr(func, "_model_validator", False):
                continue
            seen.add(attr_name)
            mode = getattr(func, "_validator_mode", "wrap")
            validators.setdefault(mode, []).append(func)
    return validators
