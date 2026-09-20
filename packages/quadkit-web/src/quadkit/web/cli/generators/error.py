"""Custom HTTP error generator for the web package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class ErrorGenerator(GeneratorBase):
    """Generate a custom HTTP error class."""

    name = "error"
    description = "Generate a custom HTTP error"
    default_output_dir = "src/errors"

    def __init__(self, output_dir: str | Path = "src/errors") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        status_code: int = 400,
        code: str | None = None,
        error_code: str | None = None,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an HTTP error module.

        Args:
            name: Error name (e.g. ``"Payment"`` or ``"payment_error"``).
            status_code: Default HTTP status code of the error.
            code: Machine-readable error code (e.g. ``"PAYMENT_ERROR"``);
                derived from *name* when omitted.
            error_code: Registry code for ``_code`` (e.g. ``"QK_ERR_WEB_100"``).
            doc: Optional module docstring note.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        snake_name = self._to_snake_case(name)
        class_name = self._to_pascal_case(name)
        content = self.render_template(
            "error.py.jinja2",
            {
                "class_name": class_name,
                "snake_name": snake_name,
                "status_code": status_code,
                "code": code or f"{snake_name.upper()}_ERROR",
                "error_code": error_code or "QK_ERR_WEB_100",
                "doc": doc,
            },
        )
        file_path = self.output_dir / f"{snake_name}_error.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["ErrorGenerator"]
