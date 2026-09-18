"""Naming utilities for CLI code generation."""

from __future__ import annotations

import re


def to_snake_case(name: str) -> str:
    """Convert a PascalCase or camelCase string to snake_case.

    Args:
        name: The string to convert.

    Returns:
        The snake_case representation.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def to_camel_case(name: str) -> str:
    """Convert snake_case to camelCase.

    Args:
        name: The snake_case string to convert.

    Returns:
        The camelCase representation.
    """
    components = name.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


__all__ = ["to_camel_case", "to_snake_case"]
