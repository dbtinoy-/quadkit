"""Seeder generator for database seed data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import pluralize_identifier, resolve_options
from quadkit.contracts.cli.parsers import EntitySpec, resolve_field_specs
from quadkit.sql.cli.generators.base import GenerationResult, GeneratorBase


class SeederGenerator(GeneratorBase):
    """Generate a database seeder file."""

    name = "seeder"
    description = "Generate a database seeder file"
    # Inside the application package rather than the project-root ``seeds/``
    # directory: a generated project boots its seeders from the persistence
    # provider, and `quadkit db seed` imports the same modules, which a file
    # outside ``src/`` cannot be. `--output seeds` still works.
    default_output_dir = "src/seeders"
    supports_entity_spec = True

    def __init__(self, output_dir: str | Path = "src/seeders") -> None:
        super().__init__(output_dir=output_dir)

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def generate(
        self,
        name: str,
        *,
        entity_spec: EntitySpec | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a database seeder module.

        Args:
            name: Singular model name (e.g. ``"User"``).
            entity_spec: Structured entity alternative to a field string.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        if entity_spec is None and isinstance(options.get("entity_spec"), EntitySpec):
            entity_spec = options["entity_spec"]
        if entity_spec is not None and self._to_snake_case(
            entity_spec.name
        ) != self._to_snake_case(name):
            raise ValueError(
                f"entity_spec.name {entity_spec.name!r} does not match "
                f"generator name {name!r}"
            )
        fields_raw = options.get("fields") or options.get("fields_str") or ""
        if fields_raw and not isinstance(fields_raw, str):
            raise TypeError("Seeder fields option must be a field-spec string")
        field_specs = resolve_field_specs(fields_raw or None, entity_spec)
        # A seed must never invent a foreign-key value: with FK
        # enforcement on, a fabricated UUID fails at insert. A nullable
        # FK samples as None; a required FK suppresses the sample row
        # entirely (the template explains why and what to author).
        required_foreign_keys = [
            spec.name for spec in field_specs if spec.fk is not None and spec.required
        ]
        fields = [
            {
                "name": spec.name,
                "type": spec.type,
                "required": spec.required,
                "unique": spec.unique,
                "fk": spec.fk,
                "default": spec.default,
                "sample_value": (
                    "None"
                    if spec.fk is not None and not spec.required
                    else self._get_sample_value(name, spec.name, spec.type)
                ),
            }
            for spec in field_specs
        ]

        model_snake = self._to_snake_case(name)
        table_name = (
            entity_spec.table_name
            if entity_spec is not None
            else pluralize_identifier(model_snake)
        )
        content = self.render_template(
            "seeder.py.jinja2",
            {
                "model_name": self._to_pascal_case(name),
                "file_name": model_snake,
                "table_name": table_name,
                "fields": fields,
                "required_foreign_keys": required_foreign_keys,
            },
        )
        file_path = self.output_dir / f"{model_snake}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    def _get_sample_value(
        self, model_name: str, field_name: str, field_type: str
    ) -> str:
        """Return a sample literal for a field, keyed by name/type heuristics."""
        lowered_type = field_type.lower()
        lowered_name = field_name.lower()
        lowered_model = model_name.lower()

        if "email" in lowered_name:
            return f'"{lowered_model}@example.com"'
        if "name" in lowered_name and "user" in lowered_name:
            return f'"John {self._to_pascal_case(model_name)}"'
        if "name" in lowered_name:
            return f'"Sample {self._to_pascal_case(model_name)}"'
        if "title" in lowered_name:
            return f'"Sample {self._to_pascal_case(model_name)} Title"'
        if "description" in lowered_name:
            return f'"This is a sample description for {lowered_model}"'
        if "url" in lowered_name or "link" in lowered_name:
            return f'"https://example.com/{lowered_model}"'
        if "phone" in lowered_name:
            return '"+1234567890"'
        if "address" in lowered_name:
            return '"123 Main St, City, Country"'
        if (
            "price" in lowered_name
            or "amount" in lowered_name
            or "cost" in lowered_name
        ):
            return "99.99"
        if "count" in lowered_name or "quantity" in lowered_name:
            return "1"
        if "age" in lowered_name:
            return "25"
        if lowered_name.startswith(("is_", "has_")) or "active" in lowered_name:
            return "True"
        if lowered_type in {"int", "integer"}:
            return "1"
        if lowered_type in {"float", "double", "decimal"}:
            return "1.0"
        if lowered_type in {"bool", "boolean"}:
            return "True"
        if lowered_type in {"date", "datetime"}:
            return "clock.now()"
        if lowered_type == "uuid":
            return '"550e8400-e29b-41d4-a716-446655440000"'
        if "json" in lowered_type:
            return '{"key": "value"}'
        return f'"sample_{lowered_name}"'


__all__ = ["SeederGenerator"]
