"""Tasks CLI contributor definitions."""

from __future__ import annotations

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    HealthCheckContribution,
    SchemaSetupContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "task",
        "Generate a background task with queue registration",
        "quadkit.tasks.cli.generators.task:TaskGenerator",
        "src/tasks",
    ),
)

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="tasks",
    )
    for name, description, generator_path, output_dir in _SPECS
)


class TasksCliContributor:
    """CLI contributor for the quadkit-tasks package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "tasks"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for tasks."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `tasks` command group."""
        return [
            CommandContribution(
                name="tasks",
                help="Background task management commands",
                app_factory_path="quadkit.tasks.cli.commands:create_tasks_app",
                contributor="tasks",
                category="extension",
                requires_app_context=True,
            ),
        ]

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return task worker health check."""
        return [
            HealthCheckContribution(
                name="task_worker_status",
                description="Check task worker process is responsive",
                check_path="quadkit.tasks.cli.checks:check_task_worker",
                contributor="tasks",
                category="tasks",
                timeout=5.0,
            ),
        ]

    def get_doctor_checks(self) -> list:
        """Return no doctor checks."""
        return []

    def get_shell_context(self) -> list:
        """Return no shell context contributions."""
        return []

    def get_hooks(self) -> list:
        """Return no hook contributions."""
        return []

    def get_schema_setup(self) -> list[SchemaSetupContribution]:
        """Return schema setup contributions for tasks."""
        return [
            SchemaSetupContribution(
                name="tasks.scheduled_jobs",
                description="Scheduled job storage",
                setup_fn_path="quadkit.tasks.cli.schema_setup:ensure_scheduled_jobs",
                contributor=self.contributor_id,
            ),
            SchemaSetupContribution(
                name="tasks.workflow_states",
                description="Workflow execution state storage",
                setup_fn_path="quadkit.tasks.cli.schema_setup:ensure_workflow_states",
                contributor=self.contributor_id,
            ),
        ]


__all__ = ["TasksCliContributor"]
