"""Field and entity specifications for CLI code generators.

The comma-separated ``--fields`` syntax is a human input format.  The
structured :class:`FieldSpec`, :class:`IndexSpec`, and :class:`EntitySpec`
objects defined here are the generator contract: callers that already have
typed entity metadata (notably the Playground) pass those objects directly
instead of serialising facts into a string and asking every generator to
parse them back.  ``parse_fields`` and ``format_fields`` are exact inverses
for the supported field modifiers, so the CLI spelling remains useful for
display and direct command-line use without becoming the internal transport.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

_FIELD_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z_][a-zA-Z0-9_]*):(?P<type>[a-zA-Z_][a-zA-Z0-9_]*)(?P<rest>.*)$",
)
_FIELD_SPLIT_PATTERN = re.compile(r",(?=\s*[a-zA-Z_][a-zA-Z0-9_]*:)")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FOREIGN_KEY_PATTERN = re.compile(
    r"^(?P<table>[A-Za-z_][A-Za-z0-9_]*)\.(?P<column>[A-Za-z_][A-Za-z0-9_]*)$"
)

#: SQL delete actions a physical foreign key may declare.  The Playground's
#: external-reference value ``none`` is deliberately absent: it means "no
#: database constraint exists", whereas ``no_action`` is the SQL action.
ON_DELETE_ACTIONS: frozenset[str] = frozenset(
    {"cascade", "restrict", "set_null", "no_action"}
)


def _require_identifier(value: str, label: str) -> None:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"Invalid {label}: {value!r}")


def _reject_text_collection(value: object, message: str) -> None:
    """Retain runtime checks for untyped callers without narrowing typed fields.

    Dataclass annotations describe normalized tuples; CLI/plugin callers can
    still pass text at runtime. Inspect it as an object rather than telling the
    type checker that a statically declared tuple can simultaneously be a str.
    """
    if isinstance(value, (str, bytes)):
        raise TypeError(message)


@dataclass(slots=True, frozen=True)
class FieldSpec:
    """Specification for one entity field.

    ``fk`` is always the table-qualified database target
    (``"<table>.<column>"``), never a model/class name.  A model name cannot
    be rendered into DDL without another naming guess, and silently guessing
    is how the original ``!fk=Model`` spelling lost constraints.
    """

    name: str
    type: str
    required: bool = True
    unique: bool = False
    indexed: bool = False
    fk: str | None = None
    on_delete: str | None = None
    default: str | None = None
    read_only: bool = False
    write_only: bool = False
    immutable: bool = False
    #: The server assigns this field from the authenticated principal on
    #: create (an ownership subject, e.g. ``author_subject``). Clients may
    #: read it but never write it: write DTOs exclude it like
    #: ``read_only``, and the controller generator injects the subject
    #: from request state so it cannot be spoofed through a request body.
    principal_assigned: bool = False

    def __post_init__(self) -> None:
        _require_identifier(self.name, "field name")
        _require_identifier(self.type, "field type")
        if self.fk is not None and not _FOREIGN_KEY_PATTERN.fullmatch(self.fk):
            raise ValueError(
                "Invalid foreign key target: expected '<table>.<column>', "
                f"got {self.fk!r}"
            )
        if self.on_delete is not None:
            normalized = self.on_delete.strip().lower()
            object.__setattr__(self, "on_delete", normalized)
            if normalized not in ON_DELETE_ACTIONS:
                allowed = ", ".join(sorted(ON_DELETE_ACTIONS))
                raise ValueError(
                    f"Invalid on_delete action {self.on_delete!r}; expected {allowed}"
                )
            if self.fk is None:
                raise ValueError("on_delete requires a foreign key target")
            if normalized == "set_null" and self.required:
                # SET NULL writes NULL on parent delete; on a NOT NULL
                # column the constraint would only fail at delete time.
                raise ValueError(
                    "on_delete=set_null requires an optional (nullable) field"
                )


@dataclass(slots=True, frozen=True)
class IndexSpec:
    """One database index over entity columns."""

    columns: tuple[str, ...]
    unique: bool = False
    name: str | None = None

    def __post_init__(self) -> None:
        _reject_text_collection(
            self.columns, "IndexSpec.columns must be an iterable of column names"
        )
        columns = tuple(self.columns)
        object.__setattr__(self, "columns", columns)
        if not columns:
            raise ValueError("IndexSpec requires at least one column")
        if len(set(columns)) != len(columns):
            raise ValueError(f"IndexSpec columns contain a duplicate: {columns!r}")
        for column in columns:
            _require_identifier(column, "index column")
        if self.name is not None:
            _require_identifier(self.name, "index name")


@dataclass(slots=True, frozen=True)
class EntitySpec:
    """Structured entity input accepted by entity-aware generators."""

    name: str
    table_name: str
    fields: tuple[FieldSpec, ...]
    indexes: tuple[IndexSpec, ...] = ()
    soft_delete: bool = False

    def __post_init__(self) -> None:
        _require_identifier(self.name, "entity name")
        _require_identifier(self.table_name, "table name")
        _reject_text_collection(
            self.fields, "EntitySpec.fields must be an iterable of FieldSpec"
        )
        _reject_text_collection(
            self.indexes, "EntitySpec.indexes must be an iterable of IndexSpec"
        )
        fields = tuple(self.fields)
        indexes = tuple(self.indexes)
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "indexes", indexes)

        seen: set[str] = set()
        duplicates: set[str] = set()
        for field in fields:
            if not isinstance(field, FieldSpec):
                raise TypeError("EntitySpec.fields must contain FieldSpec values")
            if field.name in seen:
                duplicates.add(field.name)
            seen.add(field.name)
        if duplicates:
            raise ValueError(
                f"EntitySpec {self.name!r} duplicates field(s): "
                + ", ".join(sorted(duplicates))
            )

        known_columns = seen | {"id", "created_at", "updated_at"}
        if self.soft_delete:
            known_columns.add("deleted_at")
        for index in indexes:
            if not isinstance(index, IndexSpec):
                raise TypeError("EntitySpec.indexes must contain IndexSpec values")
            unknown = [
                column for column in index.columns if column not in known_columns
            ]
            if unknown:
                raise ValueError(
                    f"EntitySpec {self.name!r} index references unknown "
                    f"column(s): {', '.join(unknown)}"
                )

    @property
    def has_foreign_keys(self) -> bool:
        """Whether any field requires physical foreign-key DDL."""

        return any(field.fk is not None for field in self.fields)


def parse_fields(fields_str: str) -> list[FieldSpec]:
    """Parse a comma-separated field spec string.

    Format::

        name:type[?][!unique][!indexed][!fk=table.column]
                     [!ondelete=cascade|restrict|set_null|no_action]
                     [!readonly][!writeonly][!immutable][!principal][=default]

    ``!read_only``/``!write_only``/``!on_delete``/``!principal_assigned``
    spellings are accepted as aliases; :func:`format_fields` emits the
    canonical compact forms above.
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


def format_fields(fields: Iterable[FieldSpec]) -> str:
    """Render structured fields in canonical CLI field-string syntax.

    This is a compatibility/display serializer only.  Structured callers
    should pass :class:`EntitySpec` to generators declaring that capability;
    the string exists so a legacy generator that needs no additional metadata
    receives exactly the same field facts the parser would produce.
    """

    parts: list[str] = []
    for field in fields:
        part = f"{field.name}:{field.type}"
        if not field.required:
            part += "?"
        if field.unique:
            part += "!unique"
        if field.indexed:
            part += "!indexed"
        if field.fk is not None:
            part += f"!fk={field.fk}"
        if field.on_delete is not None:
            part += f"!ondelete={field.on_delete}"
        if field.read_only:
            part += "!readonly"
        if field.write_only:
            part += "!writeonly"
        if field.immutable:
            part += "!immutable"
        if field.principal_assigned:
            part += "!principal"
        if field.default is not None:
            part += f"={field.default}"
        parts.append(part)
    return ",".join(parts)


def resolve_field_specs(
    fields_str: str | None = None,
    entity_spec: EntitySpec | None = None,
) -> tuple[FieldSpec, ...]:
    """Resolve legacy and structured field inputs to one field tuple.

    Supplying both is allowed only when they agree exactly.  A generator
    must never silently choose one representation and drop metadata carried
    by the other.
    """

    if entity_spec is not None and not isinstance(entity_spec, EntitySpec):
        raise TypeError("entity_spec must be an EntitySpec")
    parsed = tuple(parse_fields(fields_str)) if fields_str else ()
    if entity_spec is None:
        return parsed
    if fields_str and parsed != entity_spec.fields:
        raise ValueError(
            "fields_str and entity_spec disagree; pass only one field source "
            "or make them identical"
        )
    return entity_spec.fields


def _parse_field(field_text: str) -> FieldSpec:
    match = _FIELD_PATTERN.match(field_text)
    if match is None:
        raise ValueError(f"Invalid field specification: {field_text!r}")
    name, type_, rest = match.group("name"), match.group("type"), match.group("rest")
    required = True
    unique = False
    indexed = False
    fk: str | None = None
    on_delete: str | None = None
    default: str | None = None
    read_only = False
    write_only = False
    immutable = False
    principal_assigned = False

    if rest.startswith("?"):
        required = False
        rest = rest[1:]

    while rest:
        if rest.startswith("!unique"):
            unique = True
            rest = rest[len("!unique") :]
        elif rest.startswith("!indexed"):
            indexed = True
            rest = rest[len("!indexed") :]
        elif rest.startswith("!fk="):
            if fk is not None:
                raise ValueError(f"Invalid field specification: {field_text!r}")
            fk, rest = _parse_value_modifier(rest, "!fk=", field_text)
        elif rest.startswith("!ondelete="):
            if on_delete is not None:
                raise ValueError(f"Invalid field specification: {field_text!r}")
            on_delete, rest = _parse_value_modifier(rest, "!ondelete=", field_text)
        elif rest.startswith("!on_delete="):
            if on_delete is not None:
                raise ValueError(f"Invalid field specification: {field_text!r}")
            on_delete, rest = _parse_value_modifier(rest, "!on_delete=", field_text)
        elif rest.startswith("!readonly"):
            read_only = True
            rest = rest[len("!readonly") :]
        elif rest.startswith("!read_only"):
            read_only = True
            rest = rest[len("!read_only") :]
        elif rest.startswith("!writeonly"):
            write_only = True
            rest = rest[len("!writeonly") :]
        elif rest.startswith("!write_only"):
            write_only = True
            rest = rest[len("!write_only") :]
        elif rest.startswith("!immutable"):
            immutable = True
            rest = rest[len("!immutable") :]
        elif rest.startswith("!principal_assigned"):
            principal_assigned = True
            rest = rest[len("!principal_assigned") :]
        elif rest.startswith("!principal"):
            principal_assigned = True
            rest = rest[len("!principal") :]
        elif rest.startswith("="):
            default = rest[1:]
            rest = ""
        else:
            raise ValueError(f"Invalid field specification: {field_text!r}")

    try:
        return FieldSpec(
            name=name,
            type=type_,
            required=required,
            unique=unique,
            indexed=indexed,
            fk=fk,
            on_delete=on_delete,
            default=default,
            read_only=read_only,
            write_only=write_only,
            immutable=immutable,
            principal_assigned=principal_assigned,
        )
    except ValueError as exc:
        # Preserve the parser's established error prefix while retaining the
        # structured-spec validation detail for the operator.
        raise ValueError(
            f"Invalid field specification: {field_text!r} ({exc})"
        ) from exc


def _parse_value_modifier(
    remainder: str, prefix: str, field_text: str
) -> tuple[str, str]:
    value = remainder[len(prefix) :]
    indexes = [i for i in (value.find("!"), value.find("=")) if i != -1]
    split = min(indexes, default=-1)
    if split == -1:
        parsed, rest = value, ""
    else:
        parsed, rest = value[:split], value[split:]
    parsed = parsed.strip()
    if not parsed:
        raise ValueError(f"Invalid field specification: {field_text!r}")
    return parsed, rest


__all__ = [
    "ON_DELETE_ACTIONS",
    "EntitySpec",
    "FieldSpec",
    "IndexSpec",
    "format_fields",
    "parse_fields",
    "resolve_field_specs",
]
