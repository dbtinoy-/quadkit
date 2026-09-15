from __future__ import annotations

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.logging import get_logger

logger = get_logger(__name__)


class CoreInfrastructureProvider(Provider):
    """Provider for **shared low-level Quadkit infrastructure**.

    This is a *leaf* provider (no sub-providers) that registers the primitive
    cross-cutting services needed by every other provider:

    * ``Context`` / ``ContextVarRegistry`` — request-scoped context propagation
    * ``Registry`` — a named-object registry for ad-hoc service look-up

    **Do NOT confuse with** :class:`~quadkit.app.di.provider.CoreProvider`:

    +-----------------------------------+----------------------------------------------------+
    | ``CoreInfrastructureProvider``    | ``CoreProvider``                                   |
    +===================================+====================================================+
    | Leaf provider, no sub-providers   | Aggregating provider, no direct registrations      |
    +-----------------------------------+----------------------------------------------------+
    | Registers concrete primitives     | Delegates to sub-providers via orchestrator        |
    +-----------------------------------+----------------------------------------------------+
    | Used inside the framework         | Used by application bootstrap (``QuadkitApp``)    |
    +-----------------------------------+----------------------------------------------------+
    | ``name = "common"``               | ``name = "core"``                                  |
    +-----------------------------------+----------------------------------------------------+
    """

    name = "common"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register common utilities with the container."""
        from quadkit.contracts.core.context import RequestContextProtocol
        from quadkit.primitives.context import (
            Context,
            ContextVarRegistry,
            RequestContext,
            create_default_context,
            get_request_context,
        )
        from quadkit.primitives.registry import Registry

        context = create_default_context()
        container.singleton(Context, instance=context)
        container.singleton(ContextVarRegistry, instance=context.registry)
        # NOTE: these factories are intentionally unannotated lambdas rather
        # than ``def``s with a ``-> RequestContext | None`` return type: the
        # registration-time protocol validator only attempts to check a
        # factory's *resolved* return-type annotation, and a resolvable
        # annotation here would require ``RequestContext``/
        # ``RequestContextProtocol`` to be visible on the factory's
        # ``__globals__`` (they are only local imports of this method), which
        # would raise ``NameError`` when the validator tries to evaluate it.
        # Registration-time validation for these bindings is therefore
        # deferred to normal runtime resolution/usage, same as any other
        # protocol bound via an unannotated factory.
        container.scoped(RequestContext, lambda: get_request_context(context.registry))
        # Bind protocol to implementation
        container.scoped(
            RequestContextProtocol,  # type: ignore[type-abstract]
            lambda: get_request_context(context.registry),
        )
        container.singleton(Registry, Registry())

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Initialize common services."""
        logger.info("Quadkit Common infrastructure starting up")

    async def shutdown(self) -> None:
        """Clean up common resources."""
        logger.info("Quadkit Common infrastructure shutting down")

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check health of shared infrastructure."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "managers": ["Context", "Registry"],
                "package": "quadkit",
            },
        )


__all__ = ["CoreInfrastructureProvider"]
