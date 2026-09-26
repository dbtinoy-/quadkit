"""Pydantic entity-model generator (entity + Create/Update DTOs)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import GenerationResult, resolve_options
from quadkit.contracts.cli.parsers import parse_fields
from quadkit.sql.cli.generators.base import GeneratorBase
from quadkit.sql.cli.generators.type_map import (
    extra_dependencies,
    python_type,
    render_imports,
)


class EntityModelGenerator(GeneratorBase):
    """Generate a Pydantic entity model with Create/Update DTOs.

    Three classes are emitted for each entity:

    - ``<Name>`` — the full entity, carrying ``id`` and audit timestamps.
    - ``<Name>Create`` — the write payload; required fields stay required.
    - ``<Name>Update`` — a partial patch payload; every field is optional.
    """

    name = "domain"
    description = "Generate a Pydantic domain entity with DTOs"

    #: Fields always generated on the entity and never taken from ``--fields``.
    RESERVED_FIELDS: frozenset[str] = frozenset({"id", "created_at", "updated_at"})

    def generate(
        self,
        name: str,
        fields_str: str | None = None,
        **options: Any,
    ) -> GenerationResult:
        output_dir = options.pop("output_dir", None)
        if output_dir is not None:
            self.output_dir = Path(str(output_dir)).resolve()
        parsed = parse_fields(fields_str) if fields_str else []

        parsed = [f for f in parsed if f.name not in self.RESERVED_FIELDS]

        annotations = [python_type(f.type) for f in parsed]

        model_lines: list[str] = [
            "    id: str = Field(default_factory=lambda: uuid.uuid4().hex)",
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
            opt = "" if f.required else " | None = None"
            model_lines.append(f"    {f.name}: {py}{opt}")
            create_lines.append(f"    {f.name}: {py}{opt}")
            update_lines.append(f"    {f.name}: {py} | None = None")

        content = self.render_template(
            "entity_model.py.jinja2",
            {
                "entity_name": self._to_pascal_case(name),
                "model_name": self._to_snake_case(name),
                "import_lines": render_imports(annotations),
                "extra_dependencies": extra_dependencies(annotations),
                "fields": [
                    {
                        "name": f.name,
                        "py_type": py,
                        "required": f.required,
                    }
                    for f, py in zip(parsed, annotations, strict=True)
                ],
                "create_fields": create_lines or ["    pass"],
                "update_fields": update_lines or ["    pass"],
            },
        )

        file_path = self.output_dir / f"{self._to_snake_case(name)}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(**options)))


__all__ = ["EntityModelGenerator"]
