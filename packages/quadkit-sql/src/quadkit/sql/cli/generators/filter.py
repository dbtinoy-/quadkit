"""Exception filter generator for SQL CLI contributions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import resolve_options
from quadkit.sql.cli.generators.base import GenerationResult, GeneratorBase


class FilterGenerator(GeneratorBase):
    """Generate an exception filter."""

    name = "filter"
    description = "Generate an exception filter for error handling"
    default_output_dir = "src/filters"

    def __init__(self, output_dir: str | Path = "src/filters") -> None:
        super().__init__(output_dir=output_dir)

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def generate(
        self,
        name: str,
        *,
        exception_type: str = "Exception",
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an exception filter module.

        Args:
            name: Filter name (e.g. ``"NotFound"`` or ``"not_found"``).
            exception_type: Exception class the filter handles.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        file_path = self.output_dir / f"{self._to_snake_case(name)}.py"
        content = self.render_template(
            "filter.py.jinja2",
            {
                "name": name,
                "exception_type": exception_type,
                "snake_name": self._to_snake_case(name),
                "snake_name_plural": f"{self._to_snake_case(name)}s",
            },
        )
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["FilterGenerator"]
