"""Chained alembic migration generator for generated entities."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import GenerationResult, resolve_options
from quadkit.contracts.cli.parsers import parse_fields
from quadkit.sql.cli.generators.base import GeneratorBase
from quadkit.sql.cli.generators.type_map import sa_type


class EntityMigrationGenerator(GeneratorBase):
    """Generate an alembic revision creating the entity's table."""

    name = "migration"
    description = "Generate a chained alembic migration for an entity"

    #: Columns the template always creates. A declared field with one of these
    #: names is the *same* column, not a second one — the model generator
    #: filters the same names, and rendering both would emit a migration whose
    #: ``create_table`` lists ``id`` twice (alembic: duplicate column).
    RESERVED_FIELDS: frozenset[str] = frozenset({"id", "created_at", "updated_at"})

    def generate(
        self,
        name: str,
        fields_str: str | None = None,
        *,
        rev_id: str = "001",
        prev_rev: str | None = None,
        table_name: str | None = None,
        **options: Any,
    ) -> GenerationResult:
        output_dir = options.pop("output_dir", None)
        if output_dir is not None:
            self.output_dir = Path(str(output_dir)).resolve()
        parsed = [
            field
            for field in (parse_fields(fields_str) if fields_str else [])
            if field.name not in self.RESERVED_FIELDS
        ]
        table = table_name or f"{self._to_snake_case(name)}s"

        column_lines = [
            f'sa.Column("{f.name}",'
            f" sa.{sa_type(f.type)},"
            f" nullable={'False' if f.required else 'True'}),"
            for f in parsed
        ]

        content = self.render_template(
            "entity_migration.py.jinja2",
            {
                "rev_id": rev_id,
                "prev_rev": prev_rev,
                "table": table,
                "column_lines": column_lines,
            },
        )

        file_path = self.output_dir / f"{rev_id}_create_{table}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(**options)))
