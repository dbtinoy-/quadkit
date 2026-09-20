"""Test generator for the Quadkit CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.cli.generators.base import GenerationResult, GeneratorBase
from quadkit.cli.generators.field_parser import parse_fields
from quadkit.contracts.cli.generators import resolve_options

# Sample values for different field types
FIELD_SAMPLE_VALUES = {
    "str": '"sample_string"',
    "string": '"sample_string"',
    "text": '"sample text"',
    "int": "1",
    "integer": "1",
    "float": "1.5",
    "bool": "True",
    "boolean": "True",
    "datetime": "datetime(2024, 1, 1, tzinfo=UTC)",
}


class TestGenerator(GeneratorBase):
    """Generate a test file for domains, services, or controllers."""

    name = "test"
    description = "Generate test"
    default_output_dir = "tests/unit"
    template_name = "test_unit.py.jinja2"

    def __init__(self, output_dir: str | Path = "tests/unit") -> None:
        super().__init__(output_dir=output_dir)

    def generate(
        self,
        name: str,
        *,
        test_type: str = "domain",
        fields_str: str | None = None,
        package_name: str | None = None,
        doc: str | None = None,
        dry_run: bool = False,
        force: bool = False,
        **options: Any,
    ) -> GenerationResult:
        """Generate a test file.

        Args:
            name: The name of the module/class to test (e.g. ``"User"``).
            test_type: Type of test (domain, service, controller).
            fields_str: Field specifications for test data.
            package_name: The package name for imports.
            doc: Test documentation.
            dry_run: Compute output paths without writing.
            force: Overwrite an existing file.

        Returns:
            ``GenerationResult`` with created/skipped/overwritten paths.
        """
        model_name = self._to_snake_case(name)
        class_name = self._to_pascal_case(name)

        fields = parse_fields(fields_str or "")

        # Prepare fields with sample values
        prepared_fields = [
            {
                "name": field.name,
                "type": field.type,
                "required": field.required,
                "sample_value": FIELD_SAMPLE_VALUES.get(field.type, '"sample"'),
            }
            for field in fields
        ]

        # If no fields provided, add some defaults
        if not prepared_fields:
            prepared_fields = [
                {
                    "name": "name",
                    "type": "str",
                    "required": True,
                    "sample_value": '"Test"',
                },
                {
                    "name": "email",
                    "type": "str",
                    "required": True,
                    "sample_value": '"test@example.com"',
                },
                {
                    "name": "active",
                    "type": "bool",
                    "required": False,
                    "sample_value": "True",
                },
            ]

        context: dict[str, Any] = {
            "class_name": class_name,
            "model_name": model_name,
            "test_type": test_type,
            "package_name": package_name,
            "doc": doc,
            "fields": prepared_fields,
        }

        content = self.render_template(self.template_name, context)
        file_path = self.output_dir / f"test_{model_name}.py"
        self.stage(file_path, content)
        return self.finalize(self.commit(resolve_options(dry_run=dry_run, force=force)))


__all__ = ["TestGenerator"]
