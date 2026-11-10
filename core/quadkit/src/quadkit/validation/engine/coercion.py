"""Type coercion helpers for domain model field values.

This module provides functions for coercing values from one type to another,
particularly for handling string-to-boolean conversions and other common
type coercions used during model initialization.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Union, get_args
from uuid import UUID

# Common truthy/falsy string representations
BOOL_TRUE = frozenset({"true", "yes", "on", "1", "t", "y"})
BOOL_FALSE = frozenset({"false", "no", "off", "0", "f", "n"})


def coerce_str_to_bool(val: str) -> bool:
    """Coerce a string value to bool using common truthy/falsy words.

    Args:
        val: The string value to coerce.

    Returns:
        True for common truthy strings ("true", "yes", "on", "1", etc.).
        False for common falsy strings ("false", "no", "off", "0", etc.).

    Raises:
        ValueError: If the string cannot be coerced to a boolean.
    """
    lower = val.strip().lower()
    if lower in BOOL_TRUE:
        return True
    if lower in BOOL_FALSE:
        return False
    msg = f"Cannot coerce {val!r} to bool"
    raise ValueError(msg)


def coerce_to_bool(val: Any) -> bool:
    """Coerce any value to a boolean.

    Strings are coerced using truthy/falsy word matching.
    Other types use standard Python truthiness.

    Args:
        val: The value to coerce.

    Returns:
        The boolean representation of the value.
    """
    if isinstance(val, str):
        return coerce_str_to_bool(val)
    return bool(val)


def _extract_union_types(vtype: Any) -> list[Any]:
    """Extract individual types from a Union type (including nested).

    Args:
        vtype: A type, potentially a Union (e.g. TypeA | TypeB).

    Returns:
        List of individual types. For non-Union types, returns [vtype].
    """
    import types

    origin = getattr(vtype, "__origin__", None)
    if origin is not None and (origin is Union or isinstance(vtype, types.UnionType)):
        return list(get_args(vtype))
    if isinstance(vtype, types.UnionType):
        return list(get_args(vtype))
    return [vtype]


def _coerce_dict_value(v: Any, candidates: list[type]) -> Any:
    """Coerce a dict value to the best-matching model type.

    Scores candidates by how many input keys overlap with their dataclass
    fields, so that ``extra='ignore'`` models don't swallow dicts meant
    for a more specific type.

    Args:
        v: The value to coerce.
        candidates: List of potential model types with model_validate.

    Returns:
        The coerced value (model instance or original if no match).
    """
    if not isinstance(v, dict):
        return v

    best_score = -1
    best_result: Any = v
    for model_type in candidates:
        try:
            result = model_type.model_validate(v)  # type: ignore[attr-defined]
        except Exception:  # noqa: S112
            continue
        # Score by field overlap (higher = more specific match)
        fields = getattr(model_type, "__dataclass_fields__", {})
        score = sum(1 for k in v if k in fields) if fields else 0
        if score > best_score:
            best_score = score
            best_result = result
    return best_result


def coerce_field_value(fname: str, val: Any, type_hints: dict[str, Any], f: Any) -> Any:
    """Apply type coercion to a field value.

    Handles: UUID, datetime, Enum, bool (from str), int (from str),
    float (from str), nested DomainModel (from dict), and list[Model].

    Args:
        fname: The field name.
        val: The value to coerce.
        type_hints: The resolved type hints for the model.
        f: The dataclass field object (if available).

    Returns:
        The coerced value.
    """
    if val is None:
        return val

    # Phase 1: resolve the effective field type (best effort).
    raw_ftype: Any = None
    try:
        ftype = type_hints.get(fname, getattr(f, "type", None))
        if ftype is None:
            return val
        raw_ftype = ftype

        # Handle Optional/Union types
        origin = getattr(ftype, "__origin__", None)
        if origin is not None:
            import types

            if origin is Union or isinstance(ftype, types.UnionType):
                args = get_args(ftype)
                non_none = [t for t in args if t is not type(None)]
                if non_none:
                    ftype = non_none[0]
                    origin = getattr(ftype, "__origin__", None)
        else:
            # Python 3.10+ X | Y syntax: types.UnionType has no __origin__
            import types

            if isinstance(ftype, types.UnionType):
                args = get_args(ftype)
                non_none = [t for t in args if t is not type(None)]
                if non_none:
                    ftype = non_none[0]
                    origin = getattr(ftype, "__origin__", None)

        # list[T] coercion
        if origin is list:
            inner_args = get_args(ftype)
            if inner_args and isinstance(val, list):
                inner = inner_args[0]
                if (
                    isinstance(inner, type)
                    and hasattr(inner, "model_validate")
                    and callable(inner.model_validate)
                ):
                    val = [
                        inner.model_validate(item) if isinstance(item, dict) else item
                        for item in val
                    ]
            return val

        # dict[str, T] coercion
        if origin is dict:
            inner_args = get_args(ftype)
            if inner_args and len(inner_args) == 2 and isinstance(val, dict):
                vtype = inner_args[1]
                # Handle Union types (e.g. dict[str, TypeA | TypeB])
                union_types = _extract_union_types(vtype)
                model_candidates = [
                    t
                    for t in union_types
                    if isinstance(t, type)
                    and hasattr(t, "model_validate")
                    and callable(t.model_validate)
                ]
                if model_candidates:
                    val = {
                        k: _coerce_dict_value(v, model_candidates)
                        for k, v in val.items()
                    }
            return val

        # Literal[...] membership check
        if origin is Literal:
            allowed_literals = get_args(ftype)
            if allowed_literals and val not in allowed_literals:
                from quadkit.contracts.exceptions.domain import (
                    FieldError,
                    ValidationError,
                )

                raise ValidationError(
                    "Validation failed",
                    errors=[
                        FieldError(
                            field=fname,
                            message=(
                                f"Input should be one of {list(allowed_literals)!r}, "
                                f"got {val!r}"
                            ),
                            code="literal_error",
                        )
                    ],
                )
            return val

        # From here, ftype should be a plain type
        if not isinstance(ftype, type):
            return val
    except (ValueError, TypeError, ImportError, StopIteration):
        return val

    # Phase 2: strict bool coercion — intentionally OUTSIDE the blanket try.
    # A bool field receiving an uncoercible value (e.g. ``QK_DEBUG=garbage``)
    # is a configuration error and must fail loudly instead of silently
    # becoming a truthy string.  Must come before the int check.
    if ftype is bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return coerce_str_to_bool(val)  # raises ValueError
        if isinstance(val, int):
            return bool(val)
        return val

    # Phase 2a: strict EmailStr validation — must reject malformed emails loudly.
    email_str_cls: Any = None
    try:
        from quadkit.validation import EmailStr as _ImportedEmailStr

        email_str_cls = _ImportedEmailStr
    except ImportError:
        email_str_cls = None
    if email_str_cls is not None and ftype is email_str_cls:
        from quadkit.contracts.exceptions.domain import FieldError, ValidationError

        if not isinstance(val, str):
            raise ValidationError(
                "Validation failed",
                errors=[
                    FieldError(
                        field=fname,
                        message="Input should be a valid email address",
                        code="invalid_email",
                    )
                ],
            )
        validate_fn = getattr(email_str_cls, "_validate", None)
        try:
            if callable(validate_fn):
                return str(validate_fn(val))
        except ValueError as exc:
            raise ValidationError(
                "Validation failed",
                errors=[
                    FieldError(field=fname, message=str(exc), code="invalid_email")
                ],
            ) from exc

    # Phase 2b: strict nested model coercion when ``dict`` is not an allowed
    # union alternative on the field.  Swallowing a nested ``BaseConfig`` or
    # ``DomainModel`` validation error (for instance ``JWTConfig`` rejecting a
    # missing ``required_audience`` in production) would leave a raw ``dict``
    # bound to an attribute annotated as a typed model.
    if (
        hasattr(ftype, "model_validate")
        and callable(ftype.model_validate)
        and isinstance(val, dict)
    ):
        union_alts = _extract_union_types(raw_ftype) if raw_ftype is not None else []
        allows_raw_dict = any(
            alt is dict or getattr(alt, "__origin__", None) is dict
            for alt in union_alts
        )
        if not allows_raw_dict:
            return ftype.model_validate(val)

    # Phase 3: lenient scalar/model coercion.
    try:
        # Nested model from dict — duck-typed: any class with model_validate works
        if (
            hasattr(ftype, "model_validate")
            and callable(ftype.model_validate)
            and isinstance(val, dict)
        ):
            return ftype.model_validate(val)

        # Plain dataclass from dict (e.g. TokenUsage, ThinkingResult)
        if dataclasses.is_dataclass(ftype) and isinstance(val, dict):
            return ftype(**val)

        # UUID coercion — only for a field whose declared type *is* UUID.
        # The `fname == "id"` fallback used to fire on any annotated type, so a
        # model declaring `id: str` got a `UUID` object back while
        # `identity.generate_for` and every id column answer strings: the
        # annotation said one thing and the instance held another.
        if ftype is UUID and isinstance(val, str):
            return UUID(val)

        # datetime coercion
        if ftype is dt.datetime and isinstance(val, str):
            return dt.datetime.fromisoformat(val)

        # date coercion — a DATE column round-tripped through JSON arrives as
        # "2026-10-14", and a `date` field that keeps the string is a type lie
        # that only surfaces later (`.isoformat()`, comparisons, SQL binding).
        if ftype is dt.date and isinstance(val, str):
            return dt.date.fromisoformat(val)

        # time coercion (e.g. "09:00:00" from TIME columns or JSON)
        if ftype is dt.time and isinstance(val, str):
            return dt.time.fromisoformat(val)

        # Decimal coercion (e.g. numeric strings / floats from JSON or NUMERIC columns)
        if ftype is Decimal and isinstance(val, str | int | float):
            return Decimal(str(val))

        # Enum coercion
        if issubclass(ftype, Enum) and isinstance(val, str | int):
            return ftype(val)

        # str from scalar — pydantic's lax mode ("42" for name: str), which is
        # what `model_validate` promised before it delegated here.
        if ftype is str and isinstance(val, bool | int | float):
            return str(val)

        # str subclass coercion (e.g. SecretValue(str)) from plain str so
        # secret-typed config/domain fields preserve their redacting repr.
        if (
            issubclass(ftype, str)
            and ftype is not str
            and isinstance(val, str)
            and not isinstance(val, ftype)
        ):
            return ftype(val)

        # int coercion from str
        if ftype is int and isinstance(val, str):
            return int(val)

        # float coercion from str
        if ftype is float and isinstance(val, str):
            return float(val)

        # SecretStr coercion from str — never expose plain strings for secret fields
        from quadkit.validation import SecretStr as _SecretStr

        if ftype is _SecretStr and isinstance(val, str):
            return _SecretStr(val)

    except (ValueError, TypeError, ImportError, StopIteration):
        pass
    return val
