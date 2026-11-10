"""Serialization utilities for domain models.

This module provides functions for serializing domain models to dictionaries
and JSON, with support for common Python types like UUID, datetime, and Enum.
"""

from __future__ import annotations

import datetime as dt
from enum import Enum
from typing import Any, cast
from uuid import UUID


def json_serialize(obj: Any) -> Any:
    """Recursively convert types to JSON-serializable primitives.

    Handles:
    - dict -> dict with serialized values
    - list/tuple -> list with serialized items
    - UUID -> string
    - datetime -> ISO format string
    - Enum -> value
    - Objects with model_dump() -> recursively serialized
    - Ellipsis (...) -> None
    - Custom objects with __dict__ -> dict with serialized values
    - Callables and other non-serializable types -> str

    Args:
        obj: The object to serialize.

    Returns:
        A JSON-serializable representation of the object.
    """
    # Fast-path for JSON primitives — return as-is, no further processing needed
    if obj is None or isinstance(obj, bool | int | float | str):
        return obj
    if isinstance(obj, dict):
        return {k: json_serialize(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [json_serialize(x) for x in obj]
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dt.datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if obj is ...:
        return None
    if not callable(obj) and hasattr(obj, "__dict__"):
        return {k: json_serialize(v) for k, v in vars(obj).items()}
    return str(obj)


def _collect_computed_fields(model: Any) -> dict[str, Any]:
    """Evaluate ``@computed_field`` descriptors declared on ``type(model)``."""
    computed: dict[str, Any] = {}
    seen: set[str] = set()
    for base in type(model).__mro__:
        if base is object:
            continue
        for attr_name, descriptor in vars(base).items():
            if attr_name in seen:
                continue
            if isinstance(descriptor, property) and getattr(
                descriptor.fget, "_computed_field", False
            ):
                seen.add(attr_name)
                computed[attr_name] = getattr(model, attr_name)
    return computed


def _dump_nested_value(
    value: Any,
    *,
    mode: str,
    exclude_none: bool,
    by_alias: bool,
) -> Any:
    """Recursively dump nested DomainModel instances and plain containers."""
    if hasattr(value, "__dataclass_fields__") and hasattr(value, "model_dump"):
        return value.model_dump(
            mode=mode,
            exclude_none=exclude_none,
            by_alias=by_alias,
        )
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        nested = asdict(value)
        if exclude_none:
            nested = {k: v for k, v in nested.items() if v is not None}
        return nested
    if isinstance(value, list):
        return [
            _dump_nested_value(
                item,
                mode=mode,
                exclude_none=exclude_none,
                by_alias=by_alias,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _dump_nested_value(
                item,
                mode=mode,
                exclude_none=exclude_none,
                by_alias=by_alias,
            )
            for item in value
        )
    if isinstance(value, dict):
        return {
            k: _dump_nested_value(
                v,
                mode=mode,
                exclude_none=exclude_none,
                by_alias=by_alias,
            )
            for k, v in value.items()
        }
    return value


def model_dump_to_dict(
    model: Any,
    *,
    mode: str = "python",
    exclude: set[str] | None = None,
    include: set[str] | None = None,
    exclude_none: bool = False,
    by_alias: bool = False,
) -> dict[str, Any]:
    """Dump a model to a dictionary.

    Args:
        model: The model instance to dump.
        mode: "python" or "json" - json converts to serializable types.
        exclude: Fields to exclude from output.
        include: Fields to include in output (if None, includes all).
        exclude_none: Exclude fields whose value is ``None``.
        by_alias: Emit field aliases when configured in dataclass metadata.

    Returns:
        A dictionary representation of the model.
    """
    if hasattr(model, "__dataclass_fields__"):
        dc_fields = model.__dataclass_fields__
        data = {
            fname: _dump_nested_value(
                getattr(model, fname),
                mode="python",
                exclude_none=exclude_none,
                by_alias=by_alias,
            )
            for fname in dc_fields
            if hasattr(model, fname)
        }

        # Automatically exclude fields marked with exclude=True in metadata
        auto_exclude = {
            fname
            for fname, f in dc_fields.items()
            if getattr(f, "metadata", {}).get("exclude")
        }
        if auto_exclude:
            exclude = auto_exclude if exclude is None else exclude | auto_exclude
    else:
        dc_fields = {}
        data = dict(model.__dict__)

    # Include @computed_field properties
    for cname, cval in _collect_computed_fields(model).items():
        if cname not in data:
            data[cname] = cval

    # Add public extras from __dict__ — undeclared attributes only.
    for k, v in model.__dict__.items():
        if k not in data and not k.startswith("_"):
            data[k] = v

    if exclude:
        for field_name in exclude:
            data.pop(field_name, None)

    if include is not None:
        data = {k: v for k, v in data.items() if k in include}

    if exclude_none:
        data = {k: v for k, v in data.items() if v is not None}

    if by_alias and dc_fields:
        aliased: dict[str, Any] = {}
        for k, v in data.items():
            f = dc_fields.get(k)
            alias = getattr(f, "metadata", {}).get("alias") if f is not None else None
            aliased[alias or k] = v
        data = aliased

    if mode == "json":
        return cast("dict[str, Any]", json_serialize(data))
    return data


def get_model_extra(model: Any) -> dict[str, Any] | None:
    """Return extra fields that are not declared in the model schema.

    Analogous to pydantic's ``model_extra``. Returns ``None`` when
    there are no extra fields.

    Args:
        model: The model instance to inspect.

    Returns:
        A dictionary of extra fields, or None if there are none.
    """
    dc_fields = getattr(model, "__dataclass_fields__", None)
    if dc_fields is None:
        return None
    extras = {
        k: v
        for k, v in model.__dict__.items()
        if k not in dc_fields and not k.startswith("_")
    }
    return extras or None
