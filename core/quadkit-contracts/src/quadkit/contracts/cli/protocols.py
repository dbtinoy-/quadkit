from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.cli.contributions import (
        CommandContribution,
        DoctorCheckContribution,
        HealthCheckContribution,
        HookContribution,
        ShellContextContribution,
    )
    from quadkit.contracts.cli.types import GeneratorDefinition


@runtime_checkable
class CliContributorProtocol(Protocol):
    """Protocol for CLI contributors that register generators, commands,
    health checks, doctor checks, shell context, and hooks into the CLI.

    Each contributor is discovered via the ``quadkit.cli.contributors``
    entry point group. Install the package to make contributions available.
    """

    @property
    def contributor_id(self) -> str:
        """Unique identifier for this contributor (e.g. 'core', 'web', 'sql')."""
        ...

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return all generator definitions this contributor provides.

        Returns:
            A list of GeneratorDefinition instances. May be empty.
        """
        ...

    def get_commands(self) -> list[CommandContribution]:
        """Return CLI command groups contributed by this package.

        Returns:
            A list of CommandContribution instances. May be empty.
        """
        ...

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return runtime health checks contributed by this package.

        Health checks require a booted DI container.

        Returns:
            A list of HealthCheckContribution instances. May be empty.
        """
        ...

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return static environment/config diagnostic checks.

        Doctor checks are sync and require no container.

        Returns:
            A list of DoctorCheckContribution instances. May be empty.
        """
        ...

    def get_shell_context(self) -> list[ShellContextContribution]:
        """Return objects to inject into the interactive shell namespace.

        Returns:
            A list of ShellContextContribution instances. May be empty.
        """
        ...

    def get_hooks(self) -> list[HookContribution]:
        """Return CLI lifecycle hooks contributed by this package.

        Returns:
            A list of HookContribution instances. May be empty.
        """
        ...


__all__ = ["CliContributorProtocol"]
