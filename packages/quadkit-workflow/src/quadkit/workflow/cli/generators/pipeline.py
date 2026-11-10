"""Pipeline generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class PipelineGenerator(GeneratorBase):
    """Generate a pipeline definition."""

    name = "pipeline"
    description = "Generate a pipeline with sequential processing stages"
    default_output_dir = "src/pipelines"

    def __init__(self, output_dir: str | Path = "src/pipelines") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a pipeline module with sequential stages.

        Args:
            name: Pipeline name (e.g. ``"IngestETL"`` or ``"ingest_etl"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        pipeline_name = self._to_pascal_case(name)
        pipeline_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "pipeline_name": pipeline_name,
            "pipeline_name_snake": pipeline_snake,
        }
        content = self.render_template("pipeline.py.jinja2", context)
        file_path = self.output_dir / f"{pipeline_snake}_pipeline.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["PipelineGenerator"]
