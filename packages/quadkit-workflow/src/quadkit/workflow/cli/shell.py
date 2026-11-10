"""CLI shell context factories for quadkit-workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.workflow.di import WorkflowProvider

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol


async def provide_workflow(
    container: ContainerResolverProtocol,
) -> WorkflowProvider:
    """Provide the workflow provider for interactive shell use.

    Args:
        container: Booted DI container.

    Returns:
        The resolved workflow provider instance.
    """
    return await container.resolve(WorkflowProvider)
