"""Middleware generator for the web package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class MiddlewareGenerator(GeneratorBase):
    """Generate a middleware class."""

    name = "middleware"
    description = "Generate a web middleware component"
    default_output_dir = "src/middleware"
    template_name = "middleware.py.jinja2"

    def __init__(self, output_dir: str | Path = "src/middleware") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        doc: str | None = None,
        options: dict[str, Any] | None = None,
        dry_run: bool = False,
        force: bool = False,
        **kwargs: object,
    ) -> GenerationResult:
        """Generate a middleware module.

        Args:
            name: Middleware name (e.g. ``"Auth"`` or ``"auth"``).
            doc: Optional module docstring note.
            options: Optional configuration options for the middleware.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        file_path = self.output_dir / f"{self._to_snake_case(name)}_middleware.py"
        content = self.render_template(
            self.template_name,
            {
                "name": name,
                "class_name": f"{self._to_pascal_case(name)}Middleware",
                "doc": doc,
                "options": options,
            },
        )
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["MiddlewareGenerator"]
