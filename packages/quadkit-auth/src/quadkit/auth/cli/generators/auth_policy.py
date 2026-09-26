"""Authorization policy generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class AuthPolicyGenerator(GeneratorBase):
    """Generate an authorization policy."""

    name = "auth_policy"
    description = "Generate an authorization policy"
    default_output_dir = "src/policies"

    def __init__(self, output_dir: str | Path = "src/policies") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an authorization policy module.

        Args:
            name: Policy name (e.g. ``"ProjectAccess"`` or ``"project_access"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        policy_name = self._to_pascal_case(name)
        policy_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "policy_name": policy_name,
            "policy_name_snake": policy_snake,
        }
        content = self.render_template("auth_policy.py.jinja2", context)
        file_path = self.output_dir / f"{policy_snake}_policy.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["AuthPolicyGenerator"]
