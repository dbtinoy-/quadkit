"""GraphQL generator for the web package."""

from __future__ import annotations

from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase, parse_fields
from quadkit.contracts.cli.generators import resolve_options

GRAPHQL_TYPE_MAP = {
    "str": "str",
    "string": "str",
    "int": "int",
    "integer": "int",
    "float": "float",
    "bool": "bool",
    "boolean": "bool",
    "datetime": "datetime",
    "text": "str",
}

SAMPLE_VALUES = {
    "str": '"sample_string"',
    "string": '"sample_string"',
    "int": "1",
    "integer": "1",
    "float": "1.5",
    "bool": "True",
    "boolean": "True",
    "datetime": "datetime(2024, 1, 1, tzinfo=UTC)",
    "text": '"sample text"',
}


class GraphQLGenerator(GeneratorBase):
    """Generate a GraphQL schema scaffold."""

    template_name = "graphql.py.jinja2"

    def __init__(self, output_dir: str = "src/schema") -> None:
        super().__init__(output_dir=output_dir)

    def _build_environment(self) -> Any:
        """Use whitespace trimming for the source-oriented GraphQL template."""
        environment = super()._build_environment()
        environment.trim_blocks = True
        environment.lstrip_blocks = True
        return environment

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: object,
    ) -> GenerationResult:
        type_name = self._to_snake_case(name)
        resource_name = self._pluralize(type_name)
        file_path = self.output_dir / f"{type_name}.py"
        fields = parse_fields(fields_str or "")

        prepared_fields: list[dict[str, Any]] = []
        required_fields: list[dict[str, Any]] = []
        optional_fields: list[dict[str, Any]] = []
        filterable_fields: list[dict[str, Any]] = []

        for field in fields:
            prepared_field = {
                "name": field.name,
                "type": field.type,
                "graphql_type": GRAPHQL_TYPE_MAP.get(field.type, "str"),
                "description": f"The {field.name} field",
                "sample_value": SAMPLE_VALUES.get(field.type, '"sample"'),
            }
            prepared_fields.append(prepared_field)
            if field.required:
                required_fields.append(prepared_field)
            else:
                optional_fields.append(prepared_field)
            if field.type in {"str", "int", "bool"}:
                filterable_fields.append(prepared_field)

        if not prepared_fields:
            prepared_fields = [
                {
                    "name": "name",
                    "type": "str",
                    "graphql_type": "str",
                    "description": "The name",
                    "sample_value": '"Test"',
                },
                {
                    "name": "active",
                    "type": "bool",
                    "graphql_type": "bool",
                    "description": "Is active",
                    "sample_value": "True",
                },
            ]
            required_fields = [prepared_fields[0]]
            optional_fields = [prepared_fields[1]]
            filterable_fields = list(prepared_fields)

        content = self.render_template(
            self.template_name,
            {
                "name": name,
                "class_name": self._to_pascal_case(name),
                "singular_name": type_name,
                "resource_name": resource_name,
                "doc": doc,
                "fields": prepared_fields,
                "required_fields": required_fields,
                "optional_fields": optional_fields,
                "filterable_fields": filterable_fields,
                "include_created_at": not any(
                    field["name"] == "created_at" for field in prepared_fields
                ),
                "include_updated_at": not any(
                    field["name"] == "updated_at" for field in prepared_fields
                ),
            },
        )
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    @staticmethod
    def _pluralize(value: str) -> str:
        if value.endswith("y") and value[-2:-1] not in {"a", "e", "i", "o", "u"}:
            return f"{value[:-1]}ies"
        if value.endswith("s"):
            return value
        return f"{value}s"


__all__ = ["GraphQLGenerator"]
