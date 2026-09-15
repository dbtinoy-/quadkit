"""Webhook generator for the web package."""

from __future__ import annotations

from pathlib import Path

from quadkit.codegen import GenerationResult, GeneratorBase, parse_fields
from quadkit.contracts.cli.generators import resolve_options


class WebhookGenerator(GeneratorBase):
    """Generate a webhook handler scaffold."""

    name = "webhook"
    description = "Generate a webhook handler"
    default_output_dir = "src/webhooks"

    def __init__(self, output_dir: str | Path = "src/webhooks") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: object,
    ) -> GenerationResult:
        """Generate a webhook handler module.

        Args:
            name: Webhook name (e.g. ``"PaymentWebhook"`` or ``"payment_webhook"``).
            fields_str: Optional ``name:type`` field list in parser syntax.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        file_path = self.output_dir / f"{self._to_snake_case(name)}_webhook.py"
        content = self.render_template(
            "webhook.py.jinja2",
            {
                "webhook_name": self._to_pascal_case(name),
                "webhook_name_snake": self._to_snake_case(name),
                "package_name": self._package_name(),
                "fields": parse_fields(fields_str or ""),
            },
        )
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    def _package_name(self) -> str:
        parts = self.output_dir.parts
        if parts[:1] == ("src",):
            parts = parts[1:]
        return ".".join(parts) if parts else "app"


__all__ = ["WebhookGenerator"]
