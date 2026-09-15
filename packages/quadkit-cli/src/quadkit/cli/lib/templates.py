from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader


class TemplateRenderer:
    """Utility class to render Jinja2 templates."""

    def __init__(self, templates_dir: Path | str):
        self.templates_dir = Path(templates_dir)
        self.env = Environment(  # noqa: S701 — CLI scaffold templates, no HTML context
            loader=FileSystemLoader(str(self.templates_dir)),
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with context."""
        template = self.env.get_template(template_name)
        return template.render(context)

    def render_to_file(
        self,
        template_name: str,
        target_path: Path | str,
        context: dict[str, Any],
        overwrite: bool = False,
    ) -> Path:
        """Render a template and write it to a file."""
        target_path = Path(target_path)

        if target_path.exists() and not overwrite:
            raise FileExistsError(f"File {target_path} already exists.")

        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        content = self.render(template_name, context)
        target_path.write_text(content)
        return target_path


__all__ = ["TemplateRenderer"]
