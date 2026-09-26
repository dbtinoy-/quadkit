"""Core CLI contributor that registers the built-in framework generators."""

from __future__ import annotations

from quadkit.cli.contributors.base import (
    BaseCliContributor,
    definitions_from_specs,
)
from quadkit.contracts.cli.types import GeneratorDefinition

_GENERATOR_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "provider",
        "Generate provider",
        "quadkit.cli.generators.provider:ProviderGenerator",
        "src/di",
    ),
    (
        "test",
        (
            "Generate test; the unit test imports the domains.<name> entity "
            "that `quadkit gen domain` writes"
        ),
        "quadkit.cli.generators.test:TestGenerator",
        "tests/unit",
    ),
)


class CoreCliContributor(BaseCliContributor):
    """CLI contributor that registers all built-in framework generators."""

    @property
    def contributor_id(self) -> str:
        return "core"

    def get_generators(self) -> list[GeneratorDefinition]:
        return definitions_from_specs(
            self.contributor_id,
            _GENERATOR_SPECS,
            category="core",
        )


__all__ = ["_GENERATOR_SPECS", "CoreCliContributor"]
