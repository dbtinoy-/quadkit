"""Projection generator for the events package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class ProjectionGenerator(GeneratorBase):
    """Generate an event projection for read models."""

    name = "projection"
    description = "Generate an event projection for read models"
    default_output_dir = "src/projections"

    def __init__(self, output_dir: str | Path = "src/projections") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a projection module.

        Args:
            name: Projection name (e.g. ``"OrderSummary"`` or ``"order_summary"``).
            doc: Optional module docstring note.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        projection_name = self._to_snake_case(name)
        content = self.render_template(
            "projection.py.jinja2",
            {
                "class_name": self._to_pascal_case(name),
                "projection_name": projection_name,
                "doc": doc,
            },
        )
        file_path = self.output_dir / f"{projection_name}_projection.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["ProjectionGenerator"]
