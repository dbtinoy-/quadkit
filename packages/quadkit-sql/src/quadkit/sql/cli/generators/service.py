"""Service generator for SQL CLI contributions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import EntitySpec, pluralize_identifier, resolve_field_specs
from quadkit.contracts.cli.generators import resolve_options
from quadkit.sql.cli.generators.base import GenerationResult, GeneratorBase


class ServiceGenerator(GeneratorBase):
    """Generate an application service backed by the SQL unit of work.

    Write-only entity fields are stripped from every returned row. The
    ``validator_module``/``validator_function`` options name a
    ``validate_<entity>_payload(data) -> dict[str, str]`` function the
    rendered create/update enforce before any write; failures answer
    the field-level ``ValidationError`` (422).
    """

    name = "service"
    description = "Generate a service with unit of work"
    default_output_dir = "src/services"
    supports_entity_spec = True

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
        entity_spec: EntitySpec | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a service module.

        Args:
            name: Service name (e.g. ``"OrderService"`` or ``"order"``).
            fields_str: Optional ``name:type`` field list in parser syntax.
            entity_spec: Structured entity alternative to ``fields_str``.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        if entity_spec is not None and self._to_snake_case(
            entity_spec.name
        ) != self._to_snake_case(name):
            raise ValueError(
                f"entity_spec.name {entity_spec.name!r} does not match "
                f"generator name {name!r}"
            )
        fields = resolve_field_specs(fields_str, entity_spec)
        class_name = self._to_pascal_case(name)
        snake_name = self._to_snake_case(name)
        table_name = (
            entity_spec.table_name
            if entity_spec is not None
            else pluralize_identifier(snake_name)
        )
        context: dict[str, Any] = {
            "class_name": class_name,
            "snake_name": snake_name,
            "resource_name": table_name,
            "table_name": table_name,
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
        # Physical foreign keys drive the same integrity mapping the
        # repository template carries: a create/update that references a
        # missing row answers with a field-level validation error.
        foreign_keys = [
            {"field": field.name, "target": field.fk}
            for field in fields
            if field.fk is not None
        ]
        has_foreign_keys = bool(foreign_keys)
        # Write-only fields are accepted on write and stripped from every
        # row the rendered service returns.
        write_only_fields = [field.name for field in fields if field.write_only]
        # Validator enforcement: the caller names the payload-validator
        # module/function pair; the rendered create/update call it before
        # the unit-of-work write. Both-or-neither, so a half-named pair
        # fails loudly instead of rendering an unenforced service.
        validator_module = str(options.get("validator_module") or "")
        validator_function = str(options.get("validator_function") or "")
        if bool(validator_module) != bool(validator_function):
            raise ValueError(
                "validator_module and validator_function must be passed together"
            )
        not_found_error = str(options.get("not_found_error") or "NotFoundError")
        exceptions_module = str(
            options.get("exceptions_module") or "quadkit.contracts.exceptions"
        )
        exceptions_first_party = bool(options.get("exceptions_first_party") or False)
        # A modular app names its service-error union once in its own
        # exceptions module (``service_error_union`` option); the
        # standalone default signs the contracts union inline so the
        # integrity outcomes (409/422) are visible in every annotation.
        explicit_union = (
            str(options["service_error_union"])
            if options.get("service_error_union")
            else None
        )
        if explicit_union is not None:
            service_error_annotation = explicit_union
        else:
            parts = ["ConflictError"]
            if has_foreign_keys or validator_module:
                parts.append("ValidationError")
            parts.append(not_found_error)
            service_error_annotation = " | ".join(parts)
        context.update(
            {
                "foreign_keys": foreign_keys,
                "has_foreign_keys": has_foreign_keys,
                "write_only_fields": write_only_fields,
                "validator_module": validator_module,
                "validator_function": validator_function,
                # FieldError/ValidationError join the contracts import
                # when either integrity mapping or validator enforcement
                # renders them.
                "needs_validation_errors": has_foreign_keys or bool(validator_module),
                # One named error type per outcome, declared once: the
                # class, its import root, and the service's declared union.
                # The standalone-CLI defaults keep the contracts family;
                # a modular app passes its per-context exceptions module so
                # the lineage runs one entity-named type end to end.
                "not_found_error": not_found_error,
                "exceptions_module": exceptions_module,
                "service_error_union": explicit_union,
                "service_error_annotation": service_error_annotation,
                # Isort groups change with first-party membership: the
                # framework's contracts module sorts inside the third-party
                # block; a generated app's own exceptions module ships
                # ``[tool.ruff] src = ["src"]``, so it is first-party and
                # earns the trailing group. One template, one profile each.
                "exceptions_first_party": exceptions_first_party,
                # When the not-found error already lives in the contracts
                # exceptions module, the integrity domain errors join that
                # single import instead of opening a second line.
                "exceptions_is_contracts": (
                    exceptions_module == "quadkit.contracts.exceptions"
                    and not exceptions_first_party
                ),
            }
        )
        content = self.render_template("service.py.jinja2", context)
        file_path = self.output_dir / f"{snake_name}_service.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["ServiceGenerator"]
