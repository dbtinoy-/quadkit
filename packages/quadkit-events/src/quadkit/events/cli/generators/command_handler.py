"""Command handler generator (CQRS write side)."""

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


class CommandHandlerGenerator(GeneratorBase):
    """Generate a command handler (CQRS).

    The emitted module follows the convention demonstrated in
    ``examples/event-driven-orders``: frozen ``kw_only`` command dataclasses
    plus handlers registered explicitly on the command bus.
    """

    name = "command"
    description = "Generate a command handler (CQRS)"
    default_output_dir = "src/commands"

    def __init__(self, output_dir: str | Path = "src/commands") -> None:
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
        """Generate a command handler module.

        Args:
            name: Command name, e.g. ``"CreateUser"`` or ``"create_user"``.
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
        command_name = self._to_pascal_case(name)
        command_snake = self._to_snake_case(name)

        context: dict[str, Any] = {
            "command_name": command_name,
            "command_name_snake": command_snake,
            "fields": [
                {
                    "name": field.name,
                    "type": annotation_for(field.type),
                    "required": field.required,
                }
                for field in fields
            ],
            "imports": import_lines(
                (field.type for field in fields), always=["Any", "UUID"]
            ),
        }
        content = self.render_template("command_handler.py.jinja2", context)
        file_path = self.output_dir / f"{command_snake}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["CommandHandlerGenerator"]
