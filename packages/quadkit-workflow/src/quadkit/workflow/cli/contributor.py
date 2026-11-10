"""Workflow CLI contributor definitions."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.cli.contributions import (
    CommandContribution,
    HealthCheckContribution,
    ShellContextContribution,
)
from quadkit.contracts.cli.types import GeneratorDefinition

# (name, description, generator_path, output_dir) — titles derive via make()
_SPECS: tuple[tuple[str, str, str, str], ...] = (
    (
        "workflow_def",
        "Generate a workflow definition with steps and transitions",
        "quadkit.workflow.cli.generators.workflow_def:WorkflowDefinitionGenerator",
        "src/workflows",
    ),
    (
        "pipeline",
        "Generate a pipeline with sequential processing stages",
        "quadkit.workflow.cli.generators.pipeline:PipelineGenerator",
        "src/pipelines",
    ),
    (
        "saga_step",
        "Generate a saga step with compensating transaction",
        "quadkit.workflow.cli.generators.saga_step:SagaStepGenerator",
        "src/sagas",
    ),
)

# Titles that make() cannot derive exactly.
_TITLES: dict[str, str] = {"workflow_def": "Generate Workflow Definition"}

_GENERATOR_DEFINITIONS: tuple[GeneratorDefinition, ...] = tuple(
    GeneratorDefinition.make(
        name,
        description=description,
        generator_path=generator_path,
        output_dir=output_dir,
        contributor="workflow",
        category="workflow",
        title=_TITLES.get(name),
    )
    for name, description, generator_path, output_dir in _SPECS
)


class WorkflowCliContributor:
    """CLI contributor for the quadkit-workflow package."""

    @property
    def contributor_id(self) -> str:
        """Return the contributor identifier."""
        return "workflow"

    def get_generators(self) -> list[GeneratorDefinition]:
        """Return generator definitions for workflow."""
        return list(_GENERATOR_DEFINITIONS)

    def get_commands(self) -> list[CommandContribution]:
        """Return the contributed `workflow` command group."""
        return [
            CommandContribution(
                name="workflow",
                help="Workflow and pipeline management commands",
                app_factory_path="quadkit.workflow.cli.commands:create_workflow_app",
                contributor="workflow",
                category="workflow",
                requires_app_context=True,
            ),
        ]

    def get_health_checks(self) -> list[HealthCheckContribution]:
        """Return workflow engine health check."""
        return [
            HealthCheckContribution(
                name="workflow_engine_status",
                description="Verify workflow engine is operational",
                check_path="quadkit.workflow.cli.checks:check_workflow_engine",
                contributor="workflow",
                category="workflow",
                timeout=5.0,
            ),
        ]

    def get_doctor_checks(self) -> list[Any]:
        """Return no doctor check contributions."""
        return []

    def get_shell_context(self) -> list[ShellContextContribution]:
        """Return workflow shell context."""
        return [
            ShellContextContribution(
                name="workflow",
                description="Workflow provider for interactive use",
                factory_path="quadkit.workflow.cli.shell:provide_workflow",
                contributor="workflow",
            ),
        ]

    def get_hooks(self) -> list[Any]:
        """Return no hook contributions."""
        return []


__all__ = ["WorkflowCliContributor"]
