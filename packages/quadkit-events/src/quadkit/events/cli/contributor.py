"""Events CLI contributor definitions."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    DoctorCheckContribution,
    HealthCheckContribution,
    SchemaSetupContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "event_handler",
        "Generate an event handler with bus registration",
        "quadkit.events.cli.generators.event_handler:EventHandlerGenerator",
        "src/handlers",
    ),
    (
        "saga",
        "Generate a saga orchestrator with compensating actions",
        "quadkit.events.cli.generators.saga:SagaGenerator",
        "src/sagas",
    ),
    (
        "event",
        "Generate a domain event class",
        "quadkit.events.cli.generators.event_generator:EventGenerator",
        "src/events",
    ),
    (
        "command",
        "Generate a CQRS command handler",
        "quadkit.events.cli.generators.command_handler:CommandHandlerGenerator",
        "src/commands",
    ),
    (
        "query",
        "Generate a CQRS query handler",
        "quadkit.events.cli.generators.query_handler:QueryHandlerGenerator",
        "src/queries",
    ),
    (
        "projection",
        "Generate an event projection for read models",
        "quadkit.events.cli.generators.projection:ProjectionGenerator",
        "src/projections",
    ),
)

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="events",
        category="events",
    )
    for name, description, generator_path, output_dir in _SPECS
)


class EventsCliContributor:
    """CLI contributor for the quadkit-events package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "events"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for events."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `events` command group."""
        return [
            CommandContribution(
                name="events",
                help="Event schema and bus management commands",
                app_factory_path="quadkit.events.cli.commands:create_events_app",
                contributor="events",
                category="events",
                requires_app_context=False,
            ),
        ]

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return event bus health check."""
        return [
            HealthCheckContribution(
                name="event_bus_status",
                description="Verify event bus and store are operational",
                check_path="quadkit.events.cli.checks:check_event_bus",
                contributor="events",
                category="events",
                timeout=5.0,
            ),
        ]

    def get_doctor_checks(self) -> list[DoctorCheckContribution]:
        """Return event store configuration doctor checks."""
        return [
            DoctorCheckContribution(
                name="event_store_configured",
                description="Check event store backend is configured",
                check_path="quadkit.events.cli.doctor:check_event_store",
                contributor="events",
                category="events",
            ),
        ]

    def get_shell_context(self) -> list[ShellContextContribution]:
        """Return event bus shell context."""
        return [
            ShellContextContribution(
                name="events",
                description="Event bus for publishing/subscribing in shell",
                factory_path="quadkit.events.cli.shell:provide_event_bus",
                contributor="events",
            ),
        ]

    def get_hooks(self) -> list:
        """Return no hook contributions."""
        return []

    def get_schema_setup(self) -> list[SchemaSetupContribution]:
        """Return schema setup contributions for events."""
        return [
            SchemaSetupContribution(
                name="events.saga_records",
                description="Saga orchestration state storage",
                setup_fn_path="quadkit.events.cli.schema_setup:ensure_saga_records",
                contributor=self.contributor_id,
            ),
        ]


__all__ = ["EventsCliContributor"]
