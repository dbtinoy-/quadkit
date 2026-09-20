"""CLI contributor sub-provider — registers the contribution system into the DI container."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.cli.assembly.assembler import CommandAssembler
from quadkit.cli.contributors.discovery import populate_cli_registries
from quadkit.cli.contributors.registry import CliContributorRegistry
from quadkit.cli.registry.generator import GeneratorRegistry

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


class CliContributorSubProvider:
    """Registers and wires the CLI contribution system into the DI container."""

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind contribution-system singletons in the DI container."""
        container.singleton(CliContributorRegistry, CliContributorRegistry())
        container.singleton(GeneratorRegistry, GeneratorRegistry())
        container.singleton(CommandAssembler, factory=CommandAssembler)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Load contributors from entry points and register their generators."""
        contributor_registry: CliContributorRegistry = await container.resolve(
            CliContributorRegistry
        )
        generator_registry: GeneratorRegistry = await container.resolve(
            GeneratorRegistry
        )
        populate_cli_registries(contributor_registry, generator_registry)


__all__ = ["CliContributorSubProvider"]
