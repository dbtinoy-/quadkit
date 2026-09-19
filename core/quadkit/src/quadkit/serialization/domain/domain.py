"""Serialization utilities for domain models.

This module provides functions for serializing domain models to dictionaries
and JSON, with support for common Python types like UUID, datetime, and Enum.
"""

from __future__ import annotations

import datetime
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
    if isinstance(obj, datetime.datetime):
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


def model_dump_to_dict(
    model: Any,
    *,
    mode: str = "python",
    exclude: set[str] | None = None,
    include: set[str] | None = None,
) -> dict[str, Any]:
    """Dump a model to a dictionary.

    Args:
        model: The model instance to dump.
        mode: "python" or "json" - json converts to serializable types.
        exclude: Fields to exclude from output.
        include: Fields to include in output (if None, includes all).

    Returns:
        A dictionary representation of the model.
    """
    if hasattr(model, "__dataclass_fields__"):
        from dataclasses import asdict

        data = asdict(model)

        # Automatically exclude fields marked with exclude=True in metadata
        auto_exclude = {
            fname
            for fname, f in model.__dataclass_fields__.items()
            if getattr(f, "metadata", {}).get("exclude")
        }
        if auto_exclude:
            exclude = auto_exclude if exclude is None else exclude | auto_exclude
    else:
        data = dict(model.__dict__)

    # Add extras from __dict__
    for k, v in model.__dict__.items():
        if k not in data:
            data[k] = v

    if exclude:
        for field_name in exclude:
            data.pop(field_name, None)

    if include:
        data = {k: v for k, v in data.items() if k in include}

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
