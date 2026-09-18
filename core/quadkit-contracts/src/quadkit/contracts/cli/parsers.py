"""Field type specification parser for CLI code generators."""

from __future__ import annotations

from dataclasses import dataclass
import re

_FIELD_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z_][a-zA-Z0-9_]*):(?P<type>[a-zA-Z_][a-zA-Z0-9_]*)(?P<rest>.*)$",
)
_FIELD_SPLIT_PATTERN = re.compile(r",(?=\s*[a-zA-Z_][a-zA-Z0-9_]*:)")


@dataclass(slots=True, frozen=True)
class FieldSpec:
    """Specification for a single field parsed from a CLI field string."""

    name: str
    type: str
    required: bool = True
    unique: bool = False
    fk: str | None = None
    default: str | None = None


def parse_fields(fields_str: str) -> list[FieldSpec]:
    """Parse a comma-separated field spec string.

    Format: ``name:type[?][!unique][!fk=Model][=default]``
    """
    if not fields_str.strip():
        return []
    fields: list[FieldSpec] = []
    for raw in _FIELD_SPLIT_PATTERN.split(fields_str):
        raw = raw.strip()
        if not raw:
            raise ValueError("Invalid field specification: empty segment")
        fields.append(_parse_field(raw))
    return fields


def _parse_field(field_text: str) -> FieldSpec:
    m = _FIELD_PATTERN.match(field_text)
    if m is None:
        raise ValueError(f"Invalid field specification: {field_text!r}")
    name, type_, rest = m.group("name"), m.group("type"), m.group("rest")
    required, unique, fk, default = True, False, None, None
    if rest.startswith("?"):
        required = False
        rest = rest[1:]
    while rest:
        if rest.startswith("!unique"):
            unique = True
            rest = rest[len("!unique") :]
        elif rest.startswith("!fk="):
            fk, rest = _parse_foreign_key(rest, field_text)
        elif rest.startswith("="):
            default = rest[1:]
            rest = ""
        else:
            raise ValueError(f"Invalid field specification: {field_text!r}")
    return FieldSpec(
        name=name, type=type_, required=required, unique=unique, fk=fk, default=default
    )


def _parse_foreign_key(remainder: str, field_text: str) -> tuple[str, str]:
    value = remainder[len("!fk=") :]
    idxs = [i for i in (value.find("!"), value.find("=")) if i != -1]
    split = min(idxs, default=-1)
    if split == -1:
        fk, rest = value, ""
    else:
        fk, rest = value[:split], value[split:]
    if not fk:
        raise ValueError(f"Invalid field specification: {field_text!r}")
    return fk, rest


__all__ = ["FieldSpec", "parse_fields"]
