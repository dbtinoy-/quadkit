"""Compile declared output projections without executable expressions."""

from __future__ import annotations

import keyword
import re
from typing import Any

from quadkit.codegen import FieldSpec, annotation_for

OUTPUT_TYPES = frozenset(
    {"str", "int", "float", "bool", "uuid", "date", "datetime", "time", "json"}
)


def compile_output_fields(raw: object, fields: list[FieldSpec]) -> list[dict[str, Any]]:
    """Validate CLI output specifications, including dry runs.

    Aggregate shape is the caller's responsibility. Generated handlers validate
    projected values before persistence; nullable fields are always present.
    """
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise TypeError("output_fields must be a list")
    inputs = {field.name: field for field in fields}
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for field in raw:
        if not isinstance(field, dict) or set(field) - {
            "name",
            "type",
            "source",
            "required",
        }:
            raise ValueError(
                "output fields require name, type, source and optional required"
            )
        name, kind, source = (field.get(key) for key in ("name", "type", "source"))
        required = field.get("required", True)
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]*", name)
            or keyword.iskeyword(name)
            or name.startswith("model_")
            or name == "self"
            or name in seen
        ):
            raise ValueError(
                "output names must be unique, nonreserved ASCII snake_case"
            )
        if (
            not isinstance(kind, str)
            or kind not in OUTPUT_TYPES
            or type(required) is not bool
        ):
            raise ValueError(
                "output type must be str/int/float/bool/uuid/date/datetime/time/json and required must be boolean"
            )
        if not isinstance(source, str) or not re.fullmatch(
            r"(input|aggregate)\.[a-z][a-z0-9_]*", source
        ):
            raise ValueError("output source must be input.<name> or aggregate.<field>")
        lane, attribute = source.split(".")
        if keyword.iskeyword(attribute):
            raise ValueError("output source requires a valid field identifier")
        if lane == "input":
            input_field = inputs.get(attribute)
            if (
                input_field is None
                or annotation_for(input_field.type) != annotation_for(kind)
                or (required and not input_field.required)
            ):
                raise ValueError(
                    "output input source must match its declared type and nullability"
                )
        seen.add(name)
        result.append(
            {
                "name": name,
                "type": "str"
                if kind in {"uuid", "date", "datetime", "time"}
                else annotation_for(kind),
                "runtime_type": "dict"
                if kind == "json"
                else "str"
                if kind in {"uuid", "date", "datetime", "time"}
                else kind,
                "json": kind == "json",
                "uuid": kind == "uuid",
                "date": kind == "date",
                "datetime": kind == "datetime",
                "time": kind == "time",
                "input": attribute if lane == "input" else None,
                "required": required,
                "expression": f"command.{attribute}"
                if lane == "input"
                else f"aggregate.get({attribute!r})",
            }
        )
        if kind in {"uuid", "date", "datetime", "time", "json"}:
            projector = f"_project_{kind}" if required else f"_project_nullable_{kind}"
            result[-1]["expression"] = f"{projector}({result[-1]['expression']})"
    return result
