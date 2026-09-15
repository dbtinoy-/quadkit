"""Interceptor generator for the web package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class InterceptorGenerator(GeneratorBase):
    """Generate a web request/response interceptor."""

    name = "interceptor"
    description = "Generate a web request/response interceptor"
    default_output_dir = "src/interceptors"

    def __init__(self, output_dir: str | Path = "src/interceptors") -> None:
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
        """Generate an interceptor module.

        Args:
            name: Interceptor name (e.g. ``"AuditLog"`` or ``"audit_log"``).
            doc: Optional module docstring note.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        snake_name = self._to_snake_case(name)
        content = self.render_template(
            "interceptor.py.jinja2",
            {
                "class_name": self._to_pascal_case(name),
                "snake_name": snake_name,
                "doc": doc,
            },
        )
        file_path = self.output_dir / f"{snake_name}_interceptor.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["InterceptorGenerator"]
