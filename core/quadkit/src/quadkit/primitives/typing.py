"""Type hint resolution utilities for domain models.

This module provides helper functions for analyzing and working with
type hints, particularly for detecting Optional types and ClassVars.
"""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin


def type_allows_none(hint: Any) -> bool:
    """Return ``True`` if the type hint explicitly includes ``None`` as a valid value.

    Handles both ``typing.Optional[X]`` / ``typing.Union[X, None]`` forms and
    the Python 3.10+ ``X | None`` union syntax.

    Args:
        hint: The type hint to check.

    Returns:
        True if the hint allows None values.
    """
    origin = get_origin(hint)
    if origin is Union:
        return type(None) in get_args(hint)
    # Python 3.10+ union syntax (types.UnionType)
    if isinstance(hint, types.UnionType):
        return type(None) in get_args(hint)
    return hint is type(None)


def is_classvar(annotation: Any) -> bool:
    """Check if an annotation is a ClassVar, handling string annotations.

    Needed because `from __future__ import annotations` turns all annotations
    into strings, and `@dataclass` cannot resolve ClassVar from strings.

    Args:
        annotation: The annotation to check.

    Returns:
        True if the annotation represents a ClassVar.
    """
    import typing

    if isinstance(annotation, str):
        return "ClassVar" in annotation
    origin = getattr(annotation, "__origin__", None)
    if origin is typing.ClassVar:
        return True
    s = str(annotation)
    return "ClassVar" in s


def unwrap_optional(hint: Any) -> Any:
    """Unwrap an Optional[X] or X | None type to get the inner type.

    Args:
        hint: The type hint to unwrap.

    Returns:
        The inner type if Optional, otherwise the original hint.
    """
    origin = get_origin(hint)
    if origin is Union:
        args = get_args(hint)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    if isinstance(hint, types.UnionType):
        args = get_args(hint)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return hint


def get_list_element_type(hint: Any) -> Any | None:
    """Get the element type of a list[T] hint.

    Args:
        hint: The type hint to analyze.

    Returns:
        The element type if the hint is a list, otherwise None.
    """
    origin = get_origin(hint)
    if origin is list:
        args = get_args(hint)
        if args:
            return args[0]
    return None


def get_dict_value_type(hint: Any) -> Any | None:
    """Get the value type of a dict[K, V] hint.

    Args:
        hint: The type hint to analyze.

    Returns:
        The value type if the hint is a dict, otherwise None.
    """
    origin = get_origin(hint)
    if origin is dict:
        args = get_args(hint)
        if args and len(args) >= 2:
            return args[1]
    return None


# ---------------------------------------------------------------------------
# TypeVars and type aliases for domain-layer generics
# ---------------------------------------------------------------------------
from typing import TypeVar  # noqa: E402

EntityID = TypeVar("EntityID")
"""TypeVar for domain entity identifier types."""

T = TypeVar("T")
"""Generic TypeVar for use within the domain layer."""
