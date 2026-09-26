"""Shared field-type vocabulary for the SQL CLI generators.

Field types arrive as free-form identifiers from ``--fields`` strings
(``name:str,price:decimal,email:email``), so the mapping from a field type to
its Python annotation, SQLAlchemy column type and required imports lives here
as the single source of truth. ``model``, ``repository`` and ``migration``
generators all read from it, which keeps an entity's Pydantic model, its
repository row mapping and its table definition in agreement.

Unknown field types still fall back to ``str`` / ``String(length=255)`` so a
typo degrades to a text column rather than failing generation.
"""

from __future__ import annotations

from collections.abc import Iterable

#: Default Python annotation used for unrecognised field types.
DEFAULT_PY_TYPE = "str"

#: Default SQLAlchemy column type used for unrecognised field types.
DEFAULT_SA_TYPE = "String(length=255)"

#: Field type → Python annotation.
PY_TYPES: dict[str, str] = {
    # Text
    "str": "str",
    "string": "str",
    "text": "str",
    "slug": "str",
    "char": "str",
    "email": "EmailStr",
    "phone": "str",
    "filename": "str",
    "filepath": "str",
    "enum": "str",
    # Numeric
    "int": "int",
    "integer": "int",
    "bigint": "int",
    "smallint": "int",
    "float": "float",
    "double": "float",
    "number": "float",
    # ``decimal`` maps to ``float`` rather than ``Decimal``: SQLite has no
    # native numeric type and JSON payloads carry JSON numbers, so float keeps
    # the model, the wire format and the column in agreement.
    "decimal": "float",
    "numeric": "float",
    "money": "float",
    # Boolean / temporal
    "bool": "bool",
    "boolean": "bool",
    "datetime": "datetime",
    "timestamp": "datetime",
    "date": "date",
    "time": "time",
    # Identifiers and structured data
    "uuid": "str",
    "json": "dict[str, Any]",
    "jsonb": "dict[str, Any]",
    "dict": "dict[str, Any]",
    "bytes": "bytes",
    "blob": "bytes",
    "binary": "bytes",
    # Network types
    "url": "AnyHttpUrl",
    "uri": "AnyHttpUrl",
    "ipv4": "IPvAnyAddress",
    "ipv6": "IPvAnyAddress",
    "ip": "IPvAnyAddress",
}

#: Field type → SQLAlchemy column type expression (``sa.`` prefix omitted).
SA_TYPES: dict[str, str] = {
    "str": "String(length=255)",
    "string": "String(length=255)",
    "text": "Text",
    "slug": "String(length=255)",
    "char": "String(length=255)",
    "email": "String(length=255)",
    "phone": "String(length=64)",
    "filename": "String(length=255)",
    "filepath": "String(length=1024)",
    "enum": "String(length=64)",
    "int": "Integer",
    "integer": "Integer",
    "bigint": "BigInteger",
    "smallint": "SmallInteger",
    "float": "Float",
    "double": "Float",
    "number": "Float",
    "decimal": "Float",
    "numeric": "Float",
    "money": "Float",
    "bool": "Boolean",
    "boolean": "Boolean",
    "datetime": "DateTime(timezone=True)",
    "timestamp": "DateTime(timezone=True)",
    "date": "Date",
    "time": "Time",
    "uuid": "String(length=32)",
    "json": "JSON",
    "jsonb": "JSON",
    "dict": "JSON",
    "bytes": "LargeBinary",
    "blob": "LargeBinary",
    "binary": "LargeBinary",
    "url": "String(length=2048)",
    "uri": "String(length=2048)",
    "ipv4": "String(length=45)",
    "ipv6": "String(length=45)",
    "ip": "String(length=45)",
}

#: Annotation → ``(module, symbol)`` import required to render it.
_ANNOTATION_IMPORTS: dict[str, tuple[str, str]] = {
    "EmailStr": ("pydantic", "EmailStr"),
    "AnyHttpUrl": ("pydantic", "AnyHttpUrl"),
    "IPvAnyAddress": ("pydantic", "IPvAnyAddress"),
    "date": ("datetime", "date"),
    "time": ("datetime", "time"),
}

#: Annotation → extra distribution needed for the model to import.
_ANNOTATION_DEPENDENCIES: dict[str, str] = {
    "EmailStr": "email-validator",
}


def python_type(field_type: str) -> str:
    """Return the Python annotation for a field type.

    Args:
        field_type: The field type identifier from a ``--fields`` string.

    Returns:
        The Python annotation, defaulting to :data:`DEFAULT_PY_TYPE`.
    """
    return PY_TYPES.get(field_type, DEFAULT_PY_TYPE)


def sa_type(field_type: str) -> str:
    """Return the SQLAlchemy column type for a field type.

    Args:
        field_type: The field type identifier from a ``--fields`` string.

    Returns:
        The SQLAlchemy type expression (without the ``sa.`` prefix),
        defaulting to :data:`DEFAULT_SA_TYPE`.
    """
    return SA_TYPES.get(field_type, DEFAULT_SA_TYPE)


#: Imports every generated model needs, merged with annotation-driven ones so
#: the rendered module never repeats a module on two lines.
BASE_IMPORTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("datetime", ("datetime", "timezone")),
    ("pydantic", ("BaseModel", "ConfigDict", "Field")),
)


def render_imports(annotations: Iterable[str]) -> list[str]:
    """Return the merged import statements for a generated model module.

    Combining the always-required imports with the annotation-driven ones
    keeps each source module on a single ``from ... import ...`` line, so
    generated models stay isort-stable without a reformat pass.

    Args:
        annotations: Python annotations appearing in a generated model.

    Returns:
        Sorted ``from <module> import <symbols>`` statements. ``Any`` is
        imported whenever an annotation references it, so ``dict[str, Any]``
        renders without an undefined name.
    """
    grouped: dict[str, set[str]] = {
        module: set(symbols) for module, symbols in BASE_IMPORTS
    }
    for annotation in annotations:
        if "Any" in annotation and annotation != "Any":
            grouped.setdefault("typing", set()).add("Any")
        required = _ANNOTATION_IMPORTS.get(annotation)
        if required is not None:
            module, symbol = required
            grouped.setdefault(module, set()).add(symbol)
    return [
        f"from {module} import {', '.join(sorted(symbols))}"
        for module, symbols in sorted(grouped.items())
    ]


def extra_dependencies(annotations: Iterable[str]) -> tuple[str, ...]:
    """Return distributions a generated project must install for its models.

    ``EmailStr`` is only usable when ``email-validator`` is installed; without
    it the generated model raises at import time.

    Args:
        annotations: Python annotations appearing in a generated model.

    Returns:
        Sorted extra distribution requirements.
    """
    needed = {
        _ANNOTATION_DEPENDENCIES[annotation]
        for annotation in annotations
        if annotation in _ANNOTATION_DEPENDENCIES
    }
    return tuple(sorted(needed))


__all__ = [
    "BASE_IMPORTS",
    "DEFAULT_PY_TYPE",
    "DEFAULT_SA_TYPE",
    "PY_TYPES",
    "SA_TYPES",
    "extra_dependencies",
    "python_type",
    "render_imports",
    "sa_type",
]
