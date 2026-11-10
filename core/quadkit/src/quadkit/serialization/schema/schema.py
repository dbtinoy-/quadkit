"""JSON Schema generation utilities for domain models.

This module provides functions for converting Python types to JSON schema types
and generating JSON schemas from domain model classes.
"""

from __future__ import annotations

from enum import Enum
import types
from typing import Annotated, Any, Literal, Union, get_args, get_origin


def _unwrap_annotated(ftype: Any) -> Any:
    if get_origin(ftype) is Annotated:
        args = get_args(ftype)
        return args[0] if args else Any
    return ftype


def python_type_to_json_schema(ftype: Any) -> str:
    """Convert a Python type to its JSON schema primitive type name."""
    ftype = _unwrap_annotated(ftype)
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    origin = get_origin(ftype)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    if origin is Literal:
        args = get_args(ftype)
        if args:
            return python_type_to_json_schema(type(args[0]))
        return "string"
    if origin is Union or isinstance(ftype, types.UnionType):
        args = get_args(ftype)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return python_type_to_json_schema(non_none[0])
        return "null"

    if isinstance(ftype, type):
        if issubclass(ftype, Enum):
            return "string"
        if hasattr(ftype, "model_json_schema") or hasattr(
            ftype, "__dataclass_fields__"
        ):
            return "object"

    args = get_args(ftype)
    if args:
        return python_type_to_json_schema(args[0])

    return type_map.get(ftype, "string")


def _field_type_schema(ftype: Any) -> dict[str, Any]:
    """Build a rich JSON schema property descriptor for *ftype*."""
    ftype = _unwrap_annotated(ftype)
    origin = get_origin(ftype)

    if origin is Union or isinstance(ftype, types.UnionType):
        non_none = [a for a in get_args(ftype) if a is not type(None)]
        if len(non_none) == 1:
            return _field_type_schema(non_none[0])
        if not non_none:
            return {"type": "null"}

    if origin is Literal:
        vals = list(get_args(ftype))
        prim = python_type_to_json_schema(type(vals[0])) if vals else "string"
        return {"type": prim, "enum": vals}

    if origin is list:
        args = get_args(ftype)
        if args:
            return {"type": "array", "items": _field_type_schema(args[0])}
        return {"type": "array"}

    if origin is dict:
        return {"type": "object"}

    if isinstance(ftype, type):
        if issubclass(ftype, Enum):
            return {"type": "string", "enum": [item.value for item in ftype]}
        model_schema_fn = getattr(ftype, "model_json_schema", None)
        if callable(model_schema_fn):
            nested = model_schema_fn()
            if isinstance(nested, dict):
                return nested

    return {"type": python_type_to_json_schema(ftype)}


def build_json_schema(
    annotations: dict[str, Any],
    dc_fields: dict[str, Any],
) -> dict[str, Any]:
    """Build a JSON schema from model annotations and dataclass fields."""
    from dataclasses import MISSING

    schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    field_names = list(dc_fields.keys()) if dc_fields else list(annotations.keys())
    for name in annotations:
        if name not in field_names:
            field_names.append(name)

    for name in field_names:
        ftype = annotations.get(name, str)
        prop_schema = dict(_field_type_schema(ftype))

        if name in dc_fields:
            f = dc_fields[name]
            meta = getattr(f, "metadata", {}) or {}
            if meta.get("description"):
                prop_schema["description"] = str(meta["description"])
            if f.default is MISSING and f.default_factory is MISSING:
                schema["required"].append(name)

        schema["properties"][name] = prop_schema

    return schema
