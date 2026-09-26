"""Domain event generator for the events package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import (
    GenerationResult,
    GeneratorBase,
    annotation_for,
    import_lines,
    parse_fields,
)
from quadkit.contracts.cli.generators import resolve_options


class EventGenerator(GeneratorBase):
    """Generate a demo-aligned domain event dataclass.

    The emitted module follows the convention demonstrated in
    ``examples/event-driven-orders``: a frozen dataclass extending
    :class:`~quadkit.contracts.domain.DomainEvent` plus a ``build_*``
    helper that attaches aggregate context.
    """

    name = "event"
    description = "Generate a domain event class"
    default_output_dir = "src/events"
    template_name = "event.py.jinja2"

    def __init__(self, output_dir: str | Path = "src/events") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a domain event module.

        Args:
            name: Event name, e.g. ``"UserCreated"`` or ``"user_created"``.
            fields_str: Optional ``name:type`` field list in parser syntax.
            doc: Optional module docstring note.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        class_name = self._to_pascal_case(name).removesuffix("Event")
        if not class_name:
            class_name = self._to_pascal_case(name)
        event_name = self._to_snake_case(class_name)

        parsed = parse_fields(fields_str or "")
        context: dict[str, Any] = {
            "class_name": class_name,
            "event_name": event_name,
            "doc": doc,
            "fields": [
                {
                    "name": field.name,
                    "type": annotation_for(field.type),
                    "required": field.required,
                }
                for field in parsed
            ],
            # The templates render annotations, so they render the imports
            # those annotations need. ``UUID`` is unconditional: the build
            # helper's ``aggregate_id`` is typed by it whether or not a
            # payload field is a uuid.
            "imports": import_lines((f.type for f in parsed), always=["UUID"]),
        }
        content = self.render_template(self.template_name, context)
        file_path = self.output_dir / f"{event_name}_event.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["EventGenerator"]
