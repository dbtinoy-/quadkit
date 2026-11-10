"""Workflow definition generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class WorkflowDefinitionGenerator(GeneratorBase):
    """Generate a workflow definition."""

    name = "workflow_def"
    description = "Generate a workflow definition with steps and transitions"
    default_output_dir = "src/workflows"

    def __init__(self, output_dir: str | Path = "src/workflows") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a workflow definition module.

        Args:
            name: Workflow name (e.g. ``"OrderProcessing"`` or ``"order_processing"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        workflow_name = self._to_pascal_case(name)
        workflow_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "workflow_name": workflow_name,
            "workflow_name_snake": workflow_snake,
        }
        content = self.render_template("workflow_def.py.jinja2", context)
        file_path = self.output_dir / f"{workflow_snake}_workflow.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["WorkflowDefinitionGenerator"]
