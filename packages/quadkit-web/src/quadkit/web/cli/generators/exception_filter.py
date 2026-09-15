"""Exception filter generator for the web package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class ExceptionFilterGenerator(GeneratorBase):
    """Generate a web exception filter."""

    name = "exception_filter"
    description = "Generate a web exception filter"
    default_output_dir = "src/filters"

    def __init__(self, output_dir: str | Path = "src/filters") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        exception_type: str = "ValueError",
        status_code: int = 400,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an exception filter module.

        Args:
            name: Filter name (e.g. ``"Payment"`` or ``"payment_filter"``).
            exception_type: Exception class name the filter handles.
            status_code: HTTP status code used in the default response.
            doc: Optional module docstring note.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        snake_name = self._to_snake_case(name)
        content = self.render_template(
            "exception_filter.py.jinja2",
            {
                "class_name": self._to_pascal_case(name),
                "snake_name": snake_name,
                "exception_type": exception_type,
                "status_code": status_code,
                "doc": doc,
            },
        )
        file_path = self.output_dir / f"{snake_name}_exception_filter.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["ExceptionFilterGenerator"]
