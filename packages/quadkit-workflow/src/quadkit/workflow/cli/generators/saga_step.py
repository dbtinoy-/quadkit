"""Saga step generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class SagaStepGenerator(GeneratorBase):
    """Generate a saga step with a compensating transaction."""

    name = "saga_step"
    description = "Generate a saga step with compensating transaction"
    default_output_dir = "src/sagas"

    def __init__(self, output_dir: str | Path = "src/sagas") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a saga step module.

        Args:
            name: Step name (e.g. ``"ReserveInventory"`` or ``"reserve_inventory"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        step_name = self._to_pascal_case(name)
        step_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "step_name": step_name,
            "step_name_snake": step_snake,
        }
        content = self.render_template("saga_step.py.jinja2", context)
        file_path = self.output_dir / f"{step_snake}_saga_step.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["SagaStepGenerator"]
