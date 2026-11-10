"""Database repository generator for creating data repositories."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.cli.generators import pluralize_identifier, resolve_options
from quadkit.contracts.cli.parsers import EntitySpec, resolve_field_specs
from quadkit.sql.cli.generators.base import GenerationResult, GeneratorBase
from quadkit.sql.cli.generators.type_map import python_type


class DatabaseRepositoryGenerator(GeneratorBase):
    """Generator for creating database repositories."""

    name = "repository"
    description = "Generate a database repository"
    default_output_dir = "src/repositories"
    supports_entity_spec = True

    @staticmethod
    def _pluralize(value: str) -> str:
        return pluralize_identifier(value)

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def generate(
        self,
        name: str,
        fields_str: str | None = None,
        *,
        entity_spec: EntitySpec | None = None,
        **options: Any,
    ) -> GenerationResult:
        if entity_spec is not None and self._to_snake_case(
            entity_spec.name
        ) != self._to_snake_case(name):
            raise ValueError(
                f"entity_spec.name {entity_spec.name!r} does not match "
                f"generator name {name!r}"
            )
        table_name = str(options.get("table_name") or "") or (
            entity_spec.table_name
            if entity_spec is not None
            else self._pluralize(self._to_snake_case(name))
        )
        if entity_spec is not None and table_name != entity_spec.table_name:
            raise ValueError(
                f"table_name {table_name!r} disagrees with entity_spec "
                f"table {entity_spec.table_name!r}"
            )
        parsed_fields = list(resolve_field_specs(fields_str, entity_spec))
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
        # Physical foreign keys drive the generated repository's
        # integrity-error mapping: a create/update that references a
        # missing row answers with a field-level validation error, so
        # the template needs the field -> "table.column" target map.
        foreign_keys = [
            {"field": f.name, "target": f.fk} for f in parsed_fields if f.fk is not None
        ]
        # Write-only fields are stored but stripped from every serialized
        # row the repository returns, so no read path can leak them.
        write_only_fields = [f.name for f in parsed_fields if f.write_only]
        # JSON-valued fields: the providers JSON-encode dict/list values
        # on write (encode_bind_value is contract law) but return raw
        # rows — they cannot tell a JSON column from a TEXT one. The
        # generator can, so the rendered repository hydrates these
        # columns back to values on read; without it every JSON column
        # would leak out of GETs as an un-parsed string.
        json_fields = [f.name for f in parsed_fields if f.type == "json"]

        file_path = self.output_dir / f"{self._to_snake_case(name)}_repository.py"

        exceptions_module = str(
            options.get("exceptions_module") or "quadkit.contracts.exceptions"
        )
        exceptions_first_party = bool(options.get("exceptions_first_party") or False)

        content = self.env.get_template("database_repository.py.jinja2").render(
            repo_name=self._to_pascal_case(name),
            resource_name=table_name,
            package_name=self._get_package_name(self.output_dir),
            fields=fields,
            foreign_keys=foreign_keys,
            has_foreign_keys=bool(foreign_keys),
            write_only_fields=write_only_fields,
            json_fields=json_fields,
            entity_name=self._to_pascal_case(name),
            table_name=table_name,
            key_field=str(options.get("key_field") or "id"),
            needs_datetime=any(f["import_datetime"] for f in fields),
            # The not-found error the repository returns. The built-in
            # default is the contracts family member, so a standalone CLI
            # render behaves exactly as before; an app whose exceptions live
            # in its own module (the generated modular layout) passes the
            # class name and import root — the class is the one named type
            # for the outcome, and R6's one lineage keeps the Result
            # bridge's status mapping uniform.
            not_found_error=str(options.get("not_found_error") or "NotFoundError"),
            exceptions_module=exceptions_module,
            exceptions_first_party=exceptions_first_party,
            # When the not-found error already lives in the contracts
            # exceptions module, the integrity domain errors (conflict /
            # validation) join that single import instead of opening a
            # second line from the same module.
            exceptions_is_contracts=(
                exceptions_module == "quadkit.contracts.exceptions"
                and not exceptions_first_party
            ),
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
