"""Database repository generator for creating data repositories."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.cli.generators import resolve_options
from quadkit.contracts.cli.parsers import parse_fields
from quadkit.sql.cli.generators.base import GenerationResult, GeneratorBase
from quadkit.sql.cli.generators.type_map import python_type


class DatabaseRepositoryGenerator(GeneratorBase):
    """Generator for creating database repositories."""

    name = "repository"
    description = "Generate a database repository"
    default_output_dir = "src/repositories"

    @staticmethod
    def _pluralize(value: str) -> str:
        if value.endswith("y") and value[-2:-1] not in {"a", "e", "i", "o", "u"}:
            return f"{value[:-1]}ies"
        if value.endswith("s"):
            return value
        return f"{value}s"

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def generate(
        self,
        name: str,
        fields_str: str | None = None,
        **options: Any,
    ) -> GenerationResult:
        parsed_fields = parse_fields(fields_str) if fields_str else []
        fields = [
            {
                "name": f.name,
                "py_type": python_type(f.type),
                "required": f.required,
                "import_datetime": python_type(f.type) == "datetime",
            }
            for f in parsed_fields
        ]
        if not fields:
            fields = [
                {
                    "name": "id",
                    "py_type": "str",
                    "required": True,
                    "import_datetime": False,
                }
            ]

        file_path = self.output_dir / f"{self._to_snake_case(name)}_repository.py"

        content = self.env.get_template("database_repository.py.jinja2").render(
            repo_name=self._to_pascal_case(name),
            resource_name=self._pluralize(self._to_snake_case(name)),
            package_name=self._get_package_name(self.output_dir),
            fields=fields,
            entity_name=self._to_pascal_case(name),
            table_name=str(
                options.get("table_name") or f"{self._to_snake_case(name)}s"
            ),
            key_field=str(options.get("key_field") or "id"),
            needs_datetime=any(f["import_datetime"] for f in fields),
        )

        self.stage(file_path, content)
        return self.finalize(
            self.commit(
                resolve_options(
                    dry_run=bool(options.get("dry_run", False)),
                    force=bool(options.get("force", False)),
                )
            )
        )


__all__ = ["DatabaseRepositoryGenerator"]
