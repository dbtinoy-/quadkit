"""Authorization guard generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class AuthGuardGenerator(GeneratorBase):
    """Generate an authorization guard."""

    name = "guard"
    description = "Generate an authorization guard"
    default_output_dir = "src/guards"

    def __init__(self, output_dir: str | Path = "src/guards") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an authorization guard module.

        Args:
            name: Guard name (e.g. ``"AdminOnly"`` or ``"admin_only"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        guard_type = str(options.get("type", "role"))
        guard_name = self._to_pascal_case(name)
        guard_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "guard_name": guard_name,
            "guard_name_snake": guard_snake,
            "guard_type": guard_type,
            "package_name": self._get_package_name(self.output_dir),
        }
        content = self.render_template("guard.py.jinja2", context)
        file_path = self.output_dir / f"{guard_snake}_guard.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["AuthGuardGenerator"]
