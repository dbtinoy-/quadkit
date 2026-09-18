"""Codegen protocols for Quadkit framework."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.cli.generators import GenerationResult


@runtime_checkable
class ScaffoldGeneratorProtocol(Protocol):
    """Interactive code scaffolder invoked via CLI.

    Scaffolders are name-based generators that produce files on disk.
    They are registered via entry points and invoked by the ``quadkit generate``
    CLI command.

    Example:
        ```python
        class MyGenerator:
            name = "mygen"
            description = "Generates a mygen"

            def generate(self, name: str, **options: Any) -> GenerationResult:
                # ... create files ...
                return GenerationResult(files_created=[...])
        ```
    """

    name: str
    description: str

    def generate(self, name: str, **options: Any) -> GenerationResult:  # noqa: UP037
        """Generate files for the given name.

        Args:
            name: The name to generate code for (e.g. module name, provider name).
            **options: Additional generation parameters such as output_dir, dry_run, force.

        Returns:
            A ``GenerationResult`` describing which files were created/skipped/overwritten.
        """
        ...


@runtime_checkable
class TemplateGeneratorProtocol(Protocol):
    """Programmatic template renderer invoked by admin/plugin system.

    Template renderers are context-based generators that return rendered objects
    rather than writing to disk. They are invoked by the admin dashboard or
    plugin system when rendering configuration templates.

    Example:
        ```python
        class AuthPolicyGenerator:
            def generate(self, context: dict[str, object]) -> list[object]:
                return [
                    PolicyRule(allow=["admin:*"]),
                    PolicyRule(allow=["user:read"]),
                ]
        ```
    """

    def generate(self, context: dict[str, object]) -> list[object]:
        """Render a template with the given context.

        Args:
            context: A dictionary of template variables and their values.

        Returns:
            A list of rendered objects (e.g. policy rules, config objects).
        """
        ...


__all__ = ["ScaffoldGeneratorProtocol", "TemplateGeneratorProtocol"]
