"""Resource generator for the web package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult
from quadkit.web.cli.generators.controller import ControllerGenerator


class ResourceGenerator:
    """Generate the web-controller slice for a REST resource."""

    name = "resource"
    description = "Generate resource"
    default_output_dir = "src"
    controller_generator_class = ControllerGenerator

    def __init__(
        self,
        output_dir: str = "src",
        controller_generator_class: type[Any] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        if controller_generator_class is not None:
            self.controller_generator_class = controller_generator_class

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **kwargs: object,
    ) -> GenerationResult:
        fields_str = str(kwargs.get("fields_str", ""))
        return self.controller_generator_class(
            output_dir=self.output_dir / "controllers",
        ).generate(
            name,
            fields_str=fields_str,
            dry_run=dry_run,
            force=force,
        )


__all__ = ["ResourceGenerator"]
