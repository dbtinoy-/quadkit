"""Provider generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.cli.generators.base import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class ProviderGenerator(GeneratorBase):
    """Generate a provider class.

    The emitted provider follows the convention demonstrated in
    ``examples/*/di/provider.py``: ``register()`` declares bindings (no I/O),
    ``boot()`` resolves cross-module dependencies and rebinds concrete
    instances, and ``health_check()`` reports component readiness.
    """

    name = "provider"
    description = "Generate provider"
    default_output_dir = "src/providers"

    def __init__(self, output_dir: str | Path = "src/providers") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a provider file.

        Args:
            name: The name of the provider (e.g. ``"User"``, ``"billing"``).
            doc: Provider documentation.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        base_name = self._strip_type_suffix(name, "Provider")
        provider_name = self._to_snake_case(base_name)
        class_name = self._to_pascal_case(base_name)

        context: dict[str, Any] = {
            "class_name": class_name,
            "provider_name": provider_name,
            "doc": doc,
        }
        content = self.render_template("provider.py.jinja2", context)
        file_path = self.output_dir / f"{provider_name}_provider.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    @staticmethod
    def _strip_type_suffix(name: str, suffix: str) -> str:
        """Strip a trailing type suffix, keeping at least one character."""
        stripped = name
        if name.endswith(suffix) and len(name) > len(suffix):
            stripped = name[: -len(suffix)]
        return stripped or name


__all__ = ["ProviderGenerator"]
