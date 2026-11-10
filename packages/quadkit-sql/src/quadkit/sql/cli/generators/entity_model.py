"""Pydantic entity-model generator (entity + Create/Update DTOs)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import GenerationResult, resolve_options
from quadkit.contracts.cli.parsers import (
    EntitySpec,
    FieldSpec,
    resolve_field_specs,
)
from quadkit.sql.cli.generators.base import GeneratorBase
from quadkit.sql.cli.generators.type_map import (
    extra_dependencies,
    python_type,
    render_imports,
)


def _write_dto_line(field: FieldSpec, annotation: str, *, update: bool) -> str:
    """One Create/Update DTO field line for a client-writable field.

    A write-only field carries an explicit ``writeOnly`` schema marker,
    so generated OpenAPI documents it as request-only while read shapes
    never return it. Ordinary fields keep the plain annotation form the
    generator has always emitted.
    """
    if field.write_only:
        marker = 'json_schema_extra={"writeOnly": True}'
        if update or not field.required:
            return (
                f"    {field.name}: {annotation} | None = Field(default=None, {marker})"
            )
        return f"    {field.name}: {annotation} = Field({marker})"
    if update:
        return f"    {field.name}: {annotation} | None = None"
    opt = "" if field.required else " | None = None"
    return f"    {field.name}: {annotation}{opt}"


class EntityModelGenerator(GeneratorBase):
    """Generate a Pydantic entity model with Create/Update DTOs.

    Three classes are emitted for each entity:

    - ``<Name>`` — the full entity, carrying ``id`` and audit timestamps.
    - ``<Name>Create`` — the write payload; required fields stay required.
    - ``<Name>Update`` — a partial patch payload; every field is optional.
    """

    name = "domain"
    description = "Generate a Pydantic domain entity with DTOs"
    supports_entity_spec = True

    #: Fields always generated on the entity and never taken from ``--fields``.
    RESERVED_FIELDS: frozenset[str] = frozenset({"id", "created_at", "updated_at"})

    def generate(
        self,
        name: str,
        fields_str: str | None = None,
        *,
        entity_spec: EntitySpec | None = None,
        **options: Any,
    ) -> GenerationResult:
        output_dir = options.pop("output_dir", None)
        if output_dir is not None:
            self.output_dir = Path(str(output_dir)).resolve()
        if entity_spec is not None and self._to_snake_case(
            entity_spec.name
        ) != self._to_snake_case(name):
            raise ValueError(
                f"entity_spec.name {entity_spec.name!r} does not match "
                f"generator name {name!r}"
            )
        parsed = [
            field
            for field in resolve_field_specs(fields_str, entity_spec)
            if field.name not in self.RESERVED_FIELDS
        ]

        annotations = [python_type(f.type) for f in parsed]

        model_lines: list[str] = [
            "    id: str = Field(default_factory=lambda: str(uuid.uuid4()))",
        ]
        # Always include created_at/updated_at — the repository template
        # always generates these audit columns.
        model_lines += [
            "    created_at: datetime = Field(",
            "        default_factory=lambda: datetime.now(timezone.utc)",
            "    )",
            "    updated_at: datetime = Field(",
            "        default_factory=lambda: datetime.now(timezone.utc)",
            "    )",
        ]
        create_lines: list[str] = []
        update_lines: list[str] = []

        for f, py in zip(parsed, annotations, strict=True):
            # The entity keeps the field's natural optionality; Create mirrors
            # it for required-ness; Update is always a partial patch, so every
            # field is optional with a ``None`` default.
            #
            # Server-owned fields never appear on the write DTOs: read-only
            # fields and principal-assigned ownership subjects (the
            # controller injects those from the authenticated request, so
            # a request body can never spoof them). Write-only fields DO
            # appear, marked so read shapes and OpenAPI keep them out of
            # every response.
            opt = "" if f.required else " | None = None"
            model_lines.append(f"    {f.name}: {py}{opt}")
            client_writable = not f.read_only and not f.principal_assigned
            if client_writable:
                create_lines.append(_write_dto_line(f, py, update=False))
            if client_writable and not f.immutable:
                update_lines.append(_write_dto_line(f, py, update=True))

        template_fields = [
            {
                "name": f.name,
                "py_type": py,
                "required": f.required,
                "write_only": f.write_only,
            }
            for f, py in zip(parsed, annotations, strict=True)
        ]
        if (
            entity_spec is not None
            and entity_spec.soft_delete
            and all(field.name != "deleted_at" for field in entity_spec.fields)
        ):
            template_fields.append(
                {
                    "name": "deleted_at",
                    "py_type": "datetime",
                    "required": False,
                    "write_only": False,
                }
            )

        content = self.render_template(
            "entity_model.py.jinja2",
            {
                "entity_name": self._to_pascal_case(name),
                "model_name": self._to_snake_case(name),
                "import_lines": render_imports(annotations),
                "extra_dependencies": extra_dependencies(annotations),
                "fields": template_fields,
                "create_fields": create_lines or ["    pass"],
                "update_fields": update_lines or ["    pass"],
            },
        )

        file_path = self.output_dir / f"{self._to_snake_case(name)}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(**options)))


__all__ = ["EntityModelGenerator"]
