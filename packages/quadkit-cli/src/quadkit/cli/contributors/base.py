from __future__ import annotations

from collections.abc import Iterable

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    HookContribution,
    SchemaSetupContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition


class BaseCliContributor:
    """Base class for all CLI contributors.

    Subclass and override ``contributor_id`` and any contribution methods
    needed. All methods default to returning empty lists for backward
    compatibility with contributors that only implemented ``get_generators()``.

    Satisfies ``CliContributorProtocol`` via structural subtyping.
    """

    @property
    def contributor_id(self) -> str:
        """Unique identifier for this contributor.

        Returns:
            A string identifier, e.g. 'core', 'web', 'sql'.
        """
        raise NotImplementedError

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions contributed by this contributor.

        Returns:
            An empty list by default; override to provide generators.
        """
        return []

    def get_commands(self) -> list[CommandContribution]:
        """Return CLI command group contributions.

        Returns:
            An empty list by default; override to provide command groups.
        """
        return []

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return runtime health check contributions.

        Returns:
            An empty list by default; override to provide health checks.
        """
        return []

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return static environment/config diagnostic check contributions.

        Returns:
            An empty list by default; override to provide doctor checks.
        """
        return []

    def get_shell_context(self) -> list[ShellContextContribution]:
        """Return shell namespace injection contributions.

        Returns:
            An empty list by default; override to provide shell context.
        """
        return []

    def get_hooks(self) -> list[HookContribution]:
        """Return CLI lifecycle hook contributions.

        Returns:
            An empty list by default; override to provide hooks.
        """
        return []

    def get_schema_setup(self) -> list[SchemaSetupContribution]:
        """Return database schema setup contributions.

        Returns:
            An empty list by default; override to provide schema setup steps.
        """
        return []


def definitions_from_specs(
    contributor_id: str,
    specs: Iterable[tuple[str, str, str, str]],
    *,
    category: str = "general",
) -> list[GeneratorDefinition]:
    """Build generator definitions from compact spec tuples.

    Each spec is ``(name, description, generator_path, output_dir)``; titles
    derive conventionally via :meth:`GeneratorDefinition.make`.
    """
    return [
        GeneratorDefinition.make(
            name,
            description=description,
            generator_path=generator_path,
            output_dir=output_dir,
            contributor=contributor_id,
            category=category,
        )
        for name, description, generator_path, output_dir in specs
    ]
