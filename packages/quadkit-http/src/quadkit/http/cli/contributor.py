"""HTTP package CLI contributor."""

from __future__ import annotations

from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "api_client",
        "Generate an external API client",
        "quadkit.http.cli.generators.api_client:APIClientGenerator",
        "src/clients",
    ),
)

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="http",
    )
    for name, description, generator_path, output_dir in _SPECS
)


class HttpCliContributor:
    """CLI contributor for the quadkit-http package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "http"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for HTTP."""
        return list(_GENERATOR_DEFINITIONS)


__all__ = ["HttpCliContributor"]
