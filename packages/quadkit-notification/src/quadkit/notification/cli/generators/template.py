"""Notification template generator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import GenerationResult, GeneratorBase
from quadkit.contracts.cli.generators import resolve_options


class NotificationTemplateGenerator(GeneratorBase):
    """Generate a notification template."""

    name = "notification_template"
    description = "Generate a notification template"
    default_output_dir = "src/notifications"

    def __init__(self, output_dir: str | Path = "src/notifications") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a notification template module.

        Args:
            name: Template name (e.g. ``"PasswordReset"`` or ``"password_reset"``).
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        template_name = self._to_pascal_case(name)
        template_snake = self._to_snake_case(name)
        context: dict[str, Any] = {
            "template_name": template_name,
            "template_name_snake": template_snake,
        }
        content = self.render_template("notification_template.py.jinja2", context)
        file_path = self.output_dir / f"{template_snake}_notification_template.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["NotificationTemplateGenerator"]
