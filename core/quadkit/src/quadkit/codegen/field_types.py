"""Field-type vocabulary for the CLI code generators.

Field types arrive as free-form identifiers from ``--fields`` strings
(``order_id:uuid,total:decimal,payload:json``) and generators render them
straight into annotations -- dataclass fields, Pydantic model fields, function
signatures. Rendering the token verbatim only
works while the token happens to be a builtin: ``float`` and ``str`` are fine,
but ``uuid``, ``datetime``, ``date``, ``time`` and ``json`` are *not* names in
the generated module, so a payload carrying any of them produced a file that
raised ``NameError`` on import — the module could not even be collected by
pytest.

Two things have to agree for a field to render correctly, so they live
together here: the annotation for a token, and the import that annotation
needs. ``date`` is a ``datetime`` name, ``UUID`` is a ``uuid`` name, and
``dict[str, Any]`` needs ``Any`` — an annotation vocabulary without its import
list is how the original bug happened.

Unknown tokens fall back to themselves, matching the SQL vocabulary's stance
that a typo degrades rather than blocks generation; the difference is that a
*known* token now always renders a name that exists.

This lives in ``quadkit.codegen`` because every generator that renders a field
already imports from here (``parse_fields`` is the other half of the same
contract): the vocabulary and the parser that produces its input belong
together, and a second copy is how the two halves drift apart again.

``quadkit-sql`` keeps its own table: SQLAlchemy columns need a second mapping
(``String(length=255)``, ``Text``) that has no meaning for a payload.
"""

from __future__ import annotations

from collections.abc import Iterable
import re

#: Field type → Python annotation for a dataclass field or signature.
PY_TYPES: dict[str, str] = {
    # Text — an event payload carries values, so URL-ish tokens stay strings:
    # a domain event is a frozen dataclass, not a validated Pydantic model,
    # and importing a validator type for one field would point the dependency
    # the wrong way.
    "str": "str",
    "string": "str",
    "text": "str",
    "slug": "str",
    "char": "str",
    "email": "str",
    "phone": "str",
    "filename": "str",
    "filepath": "str",
    "enum": "str",
    "url": "str",
    "uri": "str",
    "ipv4": "str",
    "ipv6": "str",
    "ip": "str",
    # Numeric
    "int": "int",
    "integer": "int",
    "bigint": "int",
    "smallint": "int",
    "float": "float",
    "double": "float",
    "number": "float",
    "decimal": "float",
    "numeric": "float",
    "money": "float",
    # Boolean and temporal
    "bool": "bool",
    "boolean": "bool",
    "datetime": "datetime",
    "timestamp": "datetime",
    "date": "date",
    "time": "time",
    # Identifiers and structured data
    "uuid": "UUID",
    "json": "dict[str, Any]",
    "jsonb": "dict[str, Any]",
    "dict": "dict[str, Any]",
    "object": "dict[str, Any]",
    "bytes": "bytes",
    "blob": "bytes",
    "binary": "bytes",
}

#: Annotation → the module and name that provide it.
ANNOTATION_SOURCES: dict[str, tuple[str, str]] = {
    "UUID": ("uuid", "UUID"),
    "datetime": ("datetime", "datetime"),
    "date": ("datetime", "date"),
    "time": ("datetime", "time"),
    "Any": ("typing", "Any"),
}


def annotation_for(field_type: str) -> str:
    """The Python annotation for a field-spec type token."""
    return PY_TYPES.get(field_type.strip().lower(), field_type.strip())


def import_lines(
    field_types: Iterable[str], *, always: Iterable[str] = ()
) -> list[str]:
    """One import line per module needed by the rendered annotations.

    Args:
        field_types: Raw field-spec tokens from the ``--fields`` string.
        always: Annotations the template renders outside the payload — the
            event template's ``aggregate_id: UUID``, the command and query
            templates' ``Any`` — so they are imported whether or not a field
            happens to ask for them. Templates have no import machinery of
            their own; this is it.
    """
    per_module: dict[str, set[str]] = {}
    for field_type in [*field_types, *always]:
        rendered = annotation_for(field_type)
        # Scan the *rendered annotation* rather than looking the token up in a
        # second table: a composite annotation carries more than one name
        # (``dict[str, Any]`` needs ``Any``), and the names are what the file
        # has to import.
        for name, (module, _) in ANNOTATION_SOURCES.items():
            if re.search(rf"\b{name}\b", rendered):
                per_module.setdefault(module, set()).add(name)
    return [
        f"from {module} import {', '.join(sorted(names))}"
        for module, names in sorted(per_module.items())
    ]


__all__ = ["ANNOTATION_SOURCES", "PY_TYPES", "annotation_for", "import_lines"]
