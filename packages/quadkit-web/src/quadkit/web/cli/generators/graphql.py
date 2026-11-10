"""GraphQL generator for the web package."""

from __future__ import annotations

from typing import Any

from quadkit.codegen import (
    EntitySpec,
    GenerationResult,
    GeneratorBase,
    pluralize_identifier,
    resolve_field_specs,
)
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
    supports_entity_spec = True

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
        entity_spec: EntitySpec | None = None,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: object,
    ) -> GenerationResult:
        type_name = self._to_snake_case(name)
        if (
            entity_spec is not None
            and self._to_snake_case(entity_spec.name) != type_name
        ):
            raise ValueError(
                f"entity_spec.name {entity_spec.name!r} does not match "
                f"generator name {name!r}"
            )
        resource_name = (
            entity_spec.table_name
            if entity_spec is not None
            # Standalone callers historically passed an already-plural
            # resource name. Preserve that shape instead of double-
            # pluralizing it; structured specs carry the exact table.
            else type_name
            if self._singularize(type_name) != type_name
            else self._pluralize(type_name)
        )
        file_path = self.output_dir / f"{type_name}.py"
        fields = resolve_field_specs(fields_str, entity_spec)

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
                "singular_name": self._singularize(type_name),
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
    def _singularize(value: str) -> str:
        """Best-effort singular of an English noun, for a field name.

        The by-id query and the list query must not share a name: two
        ``async def`` methods with the same name in one class body are an
        F811 redefinition, and Strawberry then sees one field where the
        generator meant two. Given ``orders`` the list field is ``orders``
        and the by-id field is ``order``. A real inflection library is not
        worth a dependency for a scaffold; the common endings are handled and
        anything unrecognised is returned unchanged, which is what a singular
        input produces anyway.
        """
        if value.endswith("ies") and not value.endswith(("eies", "aies")):
            return f"{value[:-3]}y"
        for ending in ("ches", "shes", "xes", "zes", "ses"):
            if value.endswith(ending):
                return value[:-2]
        if value.endswith("s") and not value.endswith("ss"):
            return value[:-1]
        return value

    @staticmethod
    def _pluralize(value: str) -> str:
        """Pluralize a singular list-field name via the contracts rule.

        Callers reach this helper only after the already-plural guard in
        ``generate``; ``_singularize`` remains the compatibility detector
        for legacy standalone resource names, while the actual plural is
        the same final-token derivation every table and route uses.
        """

        return pluralize_identifier(value)


__all__ = ["GraphQLGenerator"]
