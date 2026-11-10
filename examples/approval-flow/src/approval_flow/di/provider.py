"""Convention followed: **Provider pattern** — ``register()`` declares singletons, ``boot()`` resolves contracts, ``health_check()`` reports readiness.

Lifecycle wiring for the Approval Flow showcase."""

from __future__ import annotations

from typing import TYPE_CHECKING

from approval_flow.config import ApprovalFlowConfig
from approval_flow.controllers.api import ApprovalFlowApiController
from approval_flow.services.flow import ApprovalFlowService
from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.contracts.workflow import StateMachineProtocol
from quadkit.di.provider import Provider
from quadkit.workflow.di.provider import WorkflowProvider

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


class ApprovalFlowProvider(Provider):
    """Bind the demo service after Quadkit WorkflowModule is registered."""

    name = "approval_flow"
    config_key: str | None = "approval_flow"
    config_model: type | None = ApprovalFlowConfig

    def __init__(self) -> None:
        super().__init__()
        self._service: ApprovalFlowService | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind the approval-flow config and API controller to the container."""
        cfg = self.config or ApprovalFlowConfig()
        container.singleton(ApprovalFlowConfig, instance=cfg)
        container.singleton(ApprovalFlowApiController, ApprovalFlowApiController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve dependencies and wire the approval flow service."""
        # Resolving the package provider makes the composition/lifecycle
        # relationship explicit: this app's service comes after WorkflowModule.
        await container.resolve(WorkflowProvider)
        config = await container.resolve(ApprovalFlowConfig)
        state_machine = await container.resolve(StateMachineProtocol)
        self._service = ApprovalFlowService(config, state_machine=state_machine)
        container.bind(
            ApprovalFlowApiController,
            ApprovalFlowApiController(service=self._service),
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return readiness status based on whether the service has booted."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY if self._service else HealthStatus.UNHEALTHY,
            category=HealthCheckCategory.READINESS,
        )


__all__ = ["ApprovalFlowProvider"]
