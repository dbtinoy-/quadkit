"""Service generator for SQL CLI contributions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import parse_fields
from quadkit.contracts.cli.generators import resolve_options
from quadkit.sql.cli.generators.base import GenerationResult, GeneratorBase


class ServiceGenerator(GeneratorBase):
    """Generate an application service backed by the SQL unit of work."""

    name = "service"
    description = "Generate a service with unit of work"
    default_output_dir = "src/services"

    def __init__(self, output_dir: str | Path = "src/services") -> None:
        super().__init__(output_dir=output_dir)

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a service module.

        Args:
            name: Service name (e.g. ``"OrderService"`` or ``"order"``).
            fields_str: Optional ``name:type`` field list in parser syntax.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        fields = parse_fields(fields_str) if fields_str else []
        class_name = self._to_pascal_case(name)
        snake_name = self._to_snake_case(name)
        context: dict[str, Any] = {
            "class_name": class_name,
            "snake_name": snake_name,
            "resource_name": f"{snake_name}s",
            "table_name": snake_name,
            "entity_class_name": f"{class_name}Entity",
            "fields": [
                {
                    "name": field.name,
                    "type": field.type,
                    "required": field.required,
                }
                for field in fields
            ],
        }
        content = self.render_template("service.py.jinja2", context)
        file_path = self.output_dir / f"{snake_name}_service.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["ServiceGenerator"]
