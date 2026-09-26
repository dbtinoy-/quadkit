"""Saga generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class SagaGenerator(GeneratorBase):
    """Generate a saga orchestrator with compensating actions."""

    name = "saga"
    description = "Generate a saga orchestrator with compensating actions"
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
        """Generate a saga orchestrator module.

        Args:
            name: Saga name, e.g. ``"OrderFulfillment"`` or ``"order_fulfillment"``.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        saga_name = self._to_pascal_case(name)
        saga_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "saga_name": saga_name,
            "saga_name_snake": saga_snake,
        }
        content = self.render_template("saga.py.jinja2", context)
        file_path = self.output_dir / f"{saga_snake}_saga.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["SagaGenerator"]
