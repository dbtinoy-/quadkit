"""Generate JSON schema from Python type hints for LLM function calling."""

from __future__ import annotations

import inspect
import types
from typing import Any, Callable, Union, get_args, get_origin, get_type_hints


def _parse_param_descriptions(docstring: str | None) -> dict[str, str]:
    """Extract parameter descriptions from a Google-style docstring.

    Parses the ``Args:`` section and returns a mapping of parameter name to
    description string.

    Args:
        docstring: Raw docstring from a function. May be None.

    Returns:
        Dict mapping each parameter name to its description text. Empty dict
        if the docstring is absent or has no ``Args:`` section.
    """
    if not docstring:
        return {}

    descriptions: dict[str, str] = {}
    in_args = False
    current_param: str | None = None
    current_desc_parts: list[str] = []

    for line in docstring.splitlines():
        stripped = line.strip()

        if stripped in ("Args:", "Arguments:", "Parameters:"):
            in_args = True
            continue

        if in_args:
            # A new top-level section (e.g. "Returns:", "Raises:") ends args block
            if stripped and not line.startswith("  ") and not line.startswith("\t"):
                if stripped.endswith(":") and " " not in stripped.rstrip(":"):
                    if current_param:
                        descriptions[current_param] = " ".join(current_desc_parts).strip()
                    in_args = False
                    current_param = None
                    current_desc_parts = []
                    continue

            # Indented continuation of previous param description
            if current_param and stripped and ":" not in stripped.split()[0]:
                current_desc_parts.append(stripped)
                continue

            # New param line: "    param_name: description text"
            if ":" in stripped:
                if current_param:
                    descriptions[current_param] = " ".join(current_desc_parts).strip()
                    current_desc_parts = []

                param, _, desc = stripped.partition(":")
                param = param.strip()
                # Remove type hint from param if present: "param_name (type):"
                if "(" in param:
                    param = param[: param.index("(")].strip()
                if param:
                    current_param = param
                    current_desc_parts = [desc.strip()] if desc.strip() else []

    if current_param:
        descriptions[current_param] = " ".join(current_desc_parts).strip()

    return descriptions


def generate_json_schema(
    func: Callable[..., Any],
) -> dict[str, Any]:
    """Generate JSON schema from a callable's signature and type hints.

    Maps Python types to JSON schema types:
      str -> string, int -> integer, float -> number,
      bool -> boolean, list -> array, dict -> object,
      Optional[T] -> nullable T

    Parameter descriptions are extracted from the function's Google-style
    docstring ``Args:`` section and included in the schema.

    Args:
        func: The callable to generate a schema for.

    Returns:
        A JSON Schema ``object`` dict with ``properties`` and ``required`` keys.
    """
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except (TypeError, NameError, AttributeError):
        hints = {}
    param_descriptions = _parse_param_descriptions(inspect.getdoc(func))
    return _build_schema(sig, hints, param_descriptions)


def _build_schema(
    sig: inspect.Signature,
    hints: dict[str, Any],
    param_descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build JSON schema from an already-extracted signature and hints.

    Args:
        sig: Parsed function signature.
        hints: Mapping of parameter name to resolved type annotation.
        param_descriptions: Optional mapping of parameter name to description
            extracted from the function docstring.

    Returns:
        JSON Schema ``object`` dict.
    """
    descriptions = param_descriptions or {}
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        param_type = hints.get(param_name)
        if param_type is not None:
            prop = _python_type_to_json_schema(param_type)
        else:
            prop = {}

        # Inject description from docstring
        if param_name in descriptions:
            prop["description"] = descriptions[param_name]

        # Add default value
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default

        properties[param_name] = prop

        # Required if no default
        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _python_type_to_json_schema(py_type: Any) -> dict[str, Any]:
    """Convert a Python type annotation to its JSON Schema equivalent.

    Handles primitives, ``list[T]``, ``dict[K, V]``, ``X | Y`` (union),
    and ``X | None`` (optional). Pydantic models are converted via
    ``model_json_schema()``.

    Args:
        py_type: A Python type annotation (from ``typing.get_type_hints``).

    Returns:
        A JSON Schema dict for the given type.
    """
    origin = get_origin(py_type)

    # X | None or Optional[X] → schema with nullable=True
    # Handles both typing.Union (Optional[X]) and 3.10+ X | None (types.UnionType)
    if origin is Union or isinstance(py_type, types.UnionType):
        args = get_args(py_type)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            optional_schema = _python_type_to_json_schema(non_none[0])
            optional_schema["nullable"] = True
            return optional_schema
        return {"anyOf": [_python_type_to_json_schema(a) for a in non_none]}

    # list[T] → {"type": "array", "items": {...}}
    if origin is list:
        item_types = get_args(py_type)
        schema: dict[str, Any] = {"type": "array"}
        if item_types:
            schema["items"] = _python_type_to_json_schema(item_types[0])
        return schema

    # set[T] → {"type": "array", "items": {...}}
    if origin is set:
        item_types = get_args(py_type)
        schema = {"type": "array"}
        if item_types:
            schema["items"] = _python_type_to_json_schema(item_types[0])
        return schema

    # dict[K, V] → {"type": "object"}
    if origin is dict:
        return {"type": "object"}

    # Pydantic models
    if hasattr(py_type, "model_json_schema"):
        return py_type.model_json_schema()

    # Plain type(None)
    if py_type is type(None):
        return {"type": "null"}

    # Annotated[T, ...] → extract inner type T
    import typing
    if origin is getattr(typing, "Annotated", type(None)) or str(origin).startswith("typing.Annotated"):
        # get_args(py_type)[0] is the base type
        args = get_args(py_type)
        if args:
            return _python_type_to_json_schema(args[0])

    # Literal[...] → {"type": "...", "enum": [...]}
    if origin is getattr(typing, "Literal", type(None)) or str(origin).startswith("typing.Literal"):
        args = get_args(py_type)
        if not args:
            return {}
        # Try to infer the type from the first value
        first_val = args[0]
        base_type = "string"
        if isinstance(first_val, int):
            base_type = "integer"
        elif isinstance(first_val, float):
            base_type = "number"
        elif isinstance(first_val, bool):
            base_type = "boolean"
            
        return {"type": base_type, "enum": list(args)}

    # enum.Enum
    import enum
    if isinstance(py_type, type) and issubclass(py_type, enum.Enum):
        values = [e.value for e in py_type]
        if not values:
            return {"type": "string"}
        
        first_val = values[0]
        base_type = "string"
        if isinstance(first_val, int):
            base_type = "integer"
        elif isinstance(first_val, float):
            base_type = "number"
        elif isinstance(first_val, bool):
            base_type = "boolean"
            
        return {"type": base_type, "enum": values}

    _PYTHON_TO_JSON: dict[type, str] = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        bytes: "string",
    }
    if py_type in _PYTHON_TO_JSON:
        return {"type": _PYTHON_TO_JSON[py_type]}

    # Unknown type — leave untyped
    return {}


# ---------------------------------------------------------------------------
# Backward-compat alias — internal callers may use _python_type_to_json
# ---------------------------------------------------------------------------

def _python_type_to_json(py_type: Any) -> str:
    """Return the JSON schema type string for a Python type.

    Legacy helper retained for internal use. Prefer
    :func:`_python_type_to_json_schema` for new code.

    Args:
        py_type: A Python type annotation.

    Returns:
        A JSON schema type string (``"string"``, ``"integer"``, etc.).
    """
    schema_dict = _python_type_to_json_schema(py_type)
    schema_type = schema_dict.get("type")
    return schema_type if isinstance(schema_type, str) else "string"
