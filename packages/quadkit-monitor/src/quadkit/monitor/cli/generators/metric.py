"""Metric generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class MetricGenerator(GeneratorBase):
    """Generate a custom metric definition."""

    name = "metric"
    description = "Generate a custom metric definition with backend registration"
    default_output_dir = "src/metrics"

    def __init__(self, output_dir: str | Path = "src/metrics") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a custom metric definition module.

        Args:
            name: Metric name (e.g. ``"OrderLatency"`` or ``"order_latency"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        metric_name = self._to_pascal_case(name)
        metric_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "metric_name": metric_name,
            "metric_name_snake": metric_snake,
        }
        content = self.render_template("metric.py.jinja2", context)
        file_path = self.output_dir / f"{metric_snake}_metric.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["MetricGenerator"]
