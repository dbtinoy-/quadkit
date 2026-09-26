"""Health check generator for SQL CLI contributions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.contracts.cli.generators import resolve_options
from quadkit.sql.cli.generators.base import GenerationResult, GeneratorBase


class HealthCheckGenerator(GeneratorBase):
    """Generate a health check."""

    name = "health"
    description = "Generate a health check for monitoring"
    default_output_dir = "src/health"

    def __init__(self, output_dir: str | Path = "src/health") -> None:
        super().__init__(output_dir=output_dir)

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def generate(
        self,
        name: str,
        *,
        critical: bool = True,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a health check module.

        Args:
            name: Check name (e.g. ``"DiskSpace"`` or ``"disk_space"``).
            critical: Whether a failure marks the app unhealthy.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        file_path = self.output_dir / f"{self._to_snake_case(name)}.py"
        content = self.render_template(
            "health_check.py.jinja2",
            {
                "name": name,
                "class_name": self._to_pascal_case(name),
                "snake_name": self._to_snake_case(name),
                "critical": critical,
            },
        )
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["HealthCheckGenerator"]
