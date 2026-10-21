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
        # `ops` rides along when the caller selected a subset. The controller
        # generator has accepted it since it learned to render a subset of
        # CRUD; dropping it here meant a resource could only ever be the full
        # five handlers, however few the caller asked for.
        ops = kwargs.get("ops")
        if ops is not None:
            if isinstance(ops, str):
                pass
            elif isinstance(ops, (list, tuple, set)):
                if not all(isinstance(operation, str) for operation in ops):
                    raise TypeError("ops must be a string or a collection of strings")
            else:
                raise TypeError("ops must be a string or a collection of strings")

        # Keep the delegated call statically typed. A dynamic ``**{"ops":
        # object}`` passed the value through at runtime but made mypy lose the
        # ControllerGenerator's accepted operation types; calling the typed
        # keyword directly keeps that contract visible and rejects malformed
        # CLI inputs above.
        return self.controller_generator_class(
            output_dir=self.output_dir / "controllers",
        ).generate(
            name,
            fields_str=fields_str,
            ops=ops,
            dry_run=dry_run,
            force=force,
        )


__all__ = ["ResourceGenerator"]
