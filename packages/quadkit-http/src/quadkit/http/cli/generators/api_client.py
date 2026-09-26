"""API client generator for creating external API client wrappers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.codegen import FieldSpec, GenerationResult, GeneratorBase, parse_fields
from quadkit.contracts.cli.generators import resolve_options


class APIClientGenerator(GeneratorBase):
    """Generate an external API client wrapper."""

    name = "api_client"
    description = "Generate an external API client"
    default_output_dir = "src/clients"

    def __init__(self, output_dir: str | Path = "src/clients") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        fields_str: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate an API client module.

        Args:
            name: Client name (e.g. ``"StripeClient"`` or ``"stripe_client"``).
            fields_str: Optional ``name:type`` field list in parser syntax.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        fields = (
            parse_fields(fields_str)
            if fields_str
            else [
                FieldSpec(name="base_url", type="str", required=True),
                FieldSpec(name="api_key", type="str", required=False),
            ]
        )
        auth_type = str(options.get("auth", "apikey"))
        client_name = self._to_pascal_case(name)
        context: dict[str, Any] = {
            "client_name": client_name,
            "client_name_snake": self._to_snake_case(name),
            "fields": fields,
            "auth_type": auth_type,
        }
        content = self.render_template("api_client.py.jinja2", context)
        file_path = self.output_dir / f"{self._to_snake_case(name)}_client.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["APIClientGenerator"]
