"""Webhook generator for the web package."""

from __future__ import annotations

from pathlib import Path

from quadkit.codegen import (
    FieldSpec,
    GenerationResult,
    GeneratorBase,
    annotation_for,
    import_lines,
    parse_fields,
)
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
        parsed = list(parse_fields(fields_str or ""))
        if parsed and not any(field.name == "event_type" for field in parsed):
            # The handler dispatches on ``webhook_payload.event_type``, so a
            # payload without that field builds a model the handler cannot
            # read: every request answers with an AttributeError wrapped in an
            # error response. Asking for fields is not asking to lose the
            # dispatch key, so it is added first unless the caller named it.
            parsed.insert(0, FieldSpec(name="event_type", type="str", required=True))
        content = self.render_template(
            "webhook.py.jinja2",
            {
                "webhook_name": self._to_pascal_case(name),
                "webhook_name_snake": self._to_snake_case(name),
                "package_name": self._package_name(),
                # The payload is a Pydantic model, so a field token has to
                # render a type Pydantic can build the model from -- a bare
                # ``decimal`` (or any other non-builtin token) makes
                # ``Payload(**data)`` raise PydanticUserError at request time.
                "fields": [
                    {
                        "name": field.name,
                        "type": annotation_for(field.type),
                        "required": field.required,
                        "description": _field_description(field),
                    }
                    for field in parsed
                ],
                # ``Any`` is used by the handler registry outside the payload,
                # so it is imported whether or not a field asks for it.
                "imports": import_lines(
                    (field.type for field in parsed), always=["Any"]
                ),
            },
        )
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))

    def _package_name(self) -> str:
        parts = self.output_dir.parts
        if parts[:1] == ("src",):
            parts = parts[1:]
        return ".".join(parts) if parts else "app"


def _field_description(field: FieldSpec) -> str:
    """Human text for a payload field, from its type token.

    The template used to fall back to the field name, which told a reader
    nothing. Nothing downstream parses this, so it only has to be true.
    """
    return field.type.replace("_", " ")


__all__ = ["WebhookGenerator"]
