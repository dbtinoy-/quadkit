"""Resource generator for the web package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import EntitySpec, GenerationResult
from quadkit.web.cli.generators.controller import ControllerGenerator


class ResourceGenerator:
    """Generate the web-controller slice for a REST resource."""

    name = "resource"
    description = "Generate resource"
    default_output_dir = "src"
    supports_entity_spec = True
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
        entity_spec: EntitySpec | None = None,
        path: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **kwargs: object,
    ) -> GenerationResult:
        if path is not None and not isinstance(path, str):
            raise TypeError("path must be a string")
        entity_spec_candidate = kwargs.get("entity_spec")
        if entity_spec is None and isinstance(entity_spec_candidate, EntitySpec):
            entity_spec = entity_spec_candidate
        fields_raw = kwargs.get("fields_str")
        if fields_raw is not None and not isinstance(fields_raw, str):
            raise TypeError("fields_str must be a string")
        fields_str: str | None = fields_raw
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

        # Validator enforcement rides along the same way: the controller
        # generator enforces the named payload validator on its write
        # handlers, so dropping the pair here would silently render an
        # unenforced resource. The pair is both-or-neither (enforced by
        # the controller generator); each member is type-checked here so
        # malformed CLI inputs fail at this boundary.
        validator_module = kwargs.get("validator_module")
        if validator_module is not None and not isinstance(validator_module, str):
            raise TypeError("validator_module must be a string")
        validator_function = kwargs.get("validator_function")
        if validator_function is not None and not isinstance(validator_function, str):
            raise TypeError("validator_function must be a string")

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
            entity_spec=entity_spec,
            # A resource is a controller at a caller-chosen base path;
            # accepting `path` and dropping it would silently serve the
            # default pluralized route instead.
            path=path,
            ops=ops,
            dry_run=dry_run,
            force=force,
            validator_module=validator_module,
            validator_function=validator_function,
        )


__all__ = ["ResourceGenerator"]
