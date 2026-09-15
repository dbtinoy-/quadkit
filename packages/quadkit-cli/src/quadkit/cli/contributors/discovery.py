from __future__ import annotations

from quadkit.cli.contributors.registry import CliContributorRegistry
from quadkit.cli.contributors.runtime import ContributorRuntime
from quadkit.cli.output import OutputManager
from quadkit.cli.registry.generator import GeneratorRegistry
from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    HookContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.protocols import CliContributorProtocol

ENTRY_POINT_GROUP = "quadkit.cli.contributors"


def load_cli_contributors() -> list[CliContributorProtocol]:
    """Load all installed CLI contributors from entry points."""
    runtime = ContributorRuntime.from_entry_points()
    output = OutputManager()
    for error in runtime.errors.values():
        output.warning(
            f"Skipping CLI contributor {error.contributor_id}: {error.exception}"
        )
    return runtime.contributors


def populate_cli_registries(
    contributor_registry: CliContributorRegistry,
    generator_registry: GeneratorRegistry,
    contributors: list[CliContributorProtocol] | None = None,
    *,
    command_registry: list[CommandContribution] | None = None,
    health_registry: list[HealthCheckContribution] | None = None,
    doctor_registry: list[DoctorCheckContribution] | None = None,
    shell_context_registry: list[ShellContextContribution] | None = None,
    hook_registry: list[HookContribution] | None = None,
) -> dict[str, list[object]]:
    """Populate registries from discovered or provided contributors.

    Returns a dict with keys: commands, health_checks, doctor_checks,
    shell_context, hooks -- each containing the aggregated contributions.
    """
    discovered_contributors = contributors
    if discovered_contributors is None:
        discovered_contributors = load_cli_contributors()

    collected: dict[str, list[object]] = {
        "commands": [],
        "health_checks": [],
        "doctor_checks": [],
        "shell_context": [],
        "hooks": [],
    }

    for contributor in discovered_contributors:
        contributor_registry.register(contributor)

        for generator_definition in contributor.get_generators():
            generator_registry.register(generator_definition)

        collected["commands"].extend(getattr(contributor, "get_commands", list)())
        collected["health_checks"].extend(
            getattr(contributor, "get_health_checks", list)()
        )
        collected["doctor_checks"].extend(
            getattr(contributor, "get_doctor_checks", list)()
        )
        collected["shell_context"].extend(
            getattr(contributor, "get_shell_context", list)()
        )
        collected["hooks"].extend(getattr(contributor, "get_hooks", list)())

    return collected


__all__ = ["ENTRY_POINT_GROUP", "load_cli_contributors", "populate_cli_registries"]
