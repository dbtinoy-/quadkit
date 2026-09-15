"""JSON Schema generation utilities for domain models.

This module provides functions for converting Python types to JSON schema types
and generating JSON schemas from domain model classes.
"""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin


def python_type_to_json_schema(ftype: Any) -> str:
    """Convert a Python type to its JSON schema equivalent.

    Handles basic types (str, int, float, bool), containers (list, dict),
    and Optional/Union types.

    Args:
        ftype: The Python type to convert.

    Returns:
        The corresponding JSON schema type string.
    """
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    # Handle Optional/Union
    origin = get_origin(ftype)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    if origin is Union or isinstance(ftype, types.UnionType):
        args = get_args(ftype)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return python_type_to_json_schema(non_none[0])
        return "null"

    args = get_args(ftype)
    if args:
        return python_type_to_json_schema(args[0])

    return type_map.get(ftype, "string")


def build_json_schema(
    annotations: dict[str, Any],
    dc_fields: dict[str, Any],
) -> dict[str, Any]:
    """Build a JSON schema from model annotations and dataclass fields.

    Args:
        annotations: The model's __annotations__ dict.
        dc_fields: The model's __dataclass_fields__ dict.

    Returns:
        A JSON schema dictionary.
    """
    from dataclasses import MISSING

    schema: dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    for name, ftype in annotations.items():
        json_type = python_type_to_json_schema(ftype)
        schema["properties"][name] = {"type": json_type}

        if name in dc_fields:
            f = dc_fields[name]
            if f.default is MISSING and f.default_factory is MISSING:
                schema["required"].append(name)

    return schema
