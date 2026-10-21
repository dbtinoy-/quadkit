"""Type hint resolution utilities for domain models.

This module provides helper functions for analyzing and working with
type hints, particularly for detecting Optional types and ClassVars.
"""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin, get_type_hints


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


# ---------------------------------------------------------------------------
# Declared-type resolution
# ---------------------------------------------------------------------------


def _typing_namespace() -> dict[str, Any]:
    """Return every public name in ``typing`` (``Any``, ``ClassVar``, …)."""
    import typing

    return {name: getattr(typing, name) for name in dir(typing)}


def _stdlib_type_namespace(module_style: bool) -> dict[str, Any]:
    """Return the stdlib names an annotation of a ``TYPE_CHECKING`` import uses.

    A module that imports its annotation types only for the type checker
    (``if TYPE_CHECKING: from datetime import datetime``) leaves nothing behind
    at runtime, so ``get_type_hints`` raises ``NameError`` and *every* field
    loses its type: no coercion, no validation, no schema. That import style is
    the house style of this repository's models, so the resolver supplies the
    small set of types the coercion engine actually acts on.

    Args:
        module_style: Whether to bind the ``datetime`` name to the module rather
            than the class, for annotations written ``datetime.datetime``.

    Returns:
        A mapping of annotation names to their runtime objects.
    """
    import datetime as _dt
    from decimal import Decimal
    from pathlib import Path
    from uuid import UUID

    names: dict[str, Any] = {
        "date": _dt.date,
        "time": _dt.time,
        "timedelta": _dt.timedelta,
        "UUID": UUID,
        "Decimal": Decimal,
        "Path": Path,
    }
    names["datetime"] = _dt if module_style else _dt.datetime
    return names


def resolve_type_hints(cls: type) -> dict[str, Any]:
    """Resolve a class's declared field types, widening the namespace until it works.

    ``from __future__ import annotations`` stores annotations as strings that
    ``get_type_hints()`` has to evaluate, and the names they use may not exist
    at runtime:

    * ``ClassVar``/``Any`` are not in a module's globals unless it imported them;
    * annotation types imported under ``TYPE_CHECKING`` are *never* there.

    Each retry adds one layer of names, so the common imports resolve without a
    runtime import of their own. Failure is non-fatal — the caller treats an
    empty mapping as "no type information" and skips coercion.

    This is the one resolver for "what types does this model declare": the
    coercion engine feeds it to ``coerce_field_value``, and the object mapper
    uses it to match a source's fields against a dataclass destination. Both
    needs are the same need, so they must not disagree about what a field is.

    Args:
        cls: The class to resolve type hints for.

    Returns:
        A dict mapping field names to their resolved types. Empty dict on failure.
    """
    import sys

    try:
        return get_type_hints(cls)
    except (NameError, AttributeError, TypeError):
        pass

    module = sys.modules.get(cls.__module__)
    module_ns = dict(vars(module)) if module else {}
    typing_ns = _typing_namespace()

    # The framework's own base classes are annotated with these (`DomainModel`
    # declares `model_config: ClassVar[ConfigDict]`), so a subclass inherits an
    # annotation whose name lives in `quadkit.validation`, not in the app module.
    validation_ns: dict[str, Any] = {}
    try:
        from quadkit import validation as _validation

        validation_ns = {
            name: getattr(_validation, name)
            for name in getattr(_validation, "__all__", ())
        }
    except ImportError:  # pragma: no cover — validation is a hard dependency
        pass

    # Named, because the bare ``{}`` third element gives mypy nothing to infer
    # the tuple's item type from.
    stdlib_namespaces: tuple[dict[str, Any], ...] = (
        _stdlib_type_namespace(module_style=False),
        _stdlib_type_namespace(module_style=True),
        {},
    )
    candidates = [
        {**typing_ns, **validation_ns, **stdlib_ns, **module_ns}
        for stdlib_ns in stdlib_namespaces
    ]
    for globalns in candidates:
        try:
            return get_type_hints(cls, globalns=globalns)
        except (NameError, AttributeError, TypeError):
            continue

    return {}
