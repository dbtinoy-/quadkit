"""Internal helpers for MCP controller schema building and URI matching."""

from __future__ import annotations

import inspect
import re
import typing
from typing import Any

__all__: list[str] = []  # Internal — not part of public API


def _build_input_schema(handler: Any) -> dict[str, Any]:
    """Build a JSON Schema object from a method's type annotations.

    Reads the signature of ``handler``, skips ``self``, and maps Python
    built-in types to JSON Schema types.

    Args:
        handler: Bound or unbound callable with type annotations.

    Returns:
        JSON Schema ``object`` dict with ``properties`` and optional ``required``.
    """
    _TYPE_MAP: dict[Any, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    sig = inspect.signature(handler)
    # Under PEP 563 (``from __future__ import annotations`` — the
    # framework's default convention) parameter annotations are *strings*,
    # so the type map below would silently match nothing and every
    # property would degrade to "string". Resolve real types via
    # get_type_hints, falling back to the raw annotation when a hint
    # cannot be resolved.
    try:
        hints: dict[str, Any] = typing.get_type_hints(handler)
    except Exception:  # noqa: BLE001 — unresolvable hints degrade to raw annotations
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        annotation = hints.get(param_name, param.annotation)
        json_type = _TYPE_MAP.get(annotation, "string")
        properties[param_name] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _match_uri_pattern(pattern: str, uri: str) -> dict[str, str] | None:
    """Match a URI against a pattern containing ``{var}`` placeholders.

    Args:
        pattern: URI template such as ``"users://{user_id}"``.
        uri: Concrete URI such as ``"users://123"``.

    Returns:
        Dict of extracted variable values, or ``None`` if no match.
    """
    # Split on {var} placeholders, escape the literal segments, then
    # rejoin with named capture groups.
    parts = re.split(r"\{(\w+)\}", pattern)
    regex = ""
    for i, segment in enumerate(parts):
        if i % 2 == 0:
            regex += re.escape(segment)
        else:
            regex += f"(?P<{segment}>[^/]+)"
    match = re.fullmatch(regex, uri)
    return match.groupdict() if match else None
