"""Query handler generator (CQRS read side)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import (
    FieldSpec,
    GenerationResult,
    GeneratorBase,
    annotation_for,
    import_lines,
    parse_fields,
)
from quadkit.contracts.cli.generators import resolve_options


class QueryHandlerGenerator(GeneratorBase):
    """Generate a query handler (CQRS).

    The emitted module follows the convention demonstrated in
    ``examples/event-driven-orders`` read side: frozen ``kw_only`` query
    dataclasses plus handlers that never mutate state.
    """

    name = "query"
    description = "Generate a query handler (CQRS)"
    default_output_dir = "src/queries"

    def __init__(self, output_dir: str | Path = "src/queries") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a query handler module.

        Args:
            name: Query name, e.g. ``"GetUser"`` or ``"get_user"``.
            fields_str: Optional ``name:type`` field list in parser syntax.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        fields: list[FieldSpec] = (
            parse_fields(fields_str)
            if fields_str
            else [FieldSpec(name="id", type="str", required=False)]
        )
        query_name = self._to_pascal_case(name)
        query_snake = self._to_snake_case(name)

        context: dict[str, Any] = {
            "query_name": query_name,
            "query_name_snake": query_snake,
            "fields": [
                {
                    "name": field.name,
                    "type": annotation_for(field.type),
                    "required": field.required,
                }
                for field in fields
            ],
            "imports": import_lines((field.type for field in fields), always=["Any"]),
        }
        content = self.render_template("query_handler.py.jinja2", context)
        file_path = self.output_dir / f"{query_snake}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["QueryHandlerGenerator"]
