"""Base provider for Quadkit Framework.

Providers are the composition root of a Quadkit application.  Each provider
is responsible for a single bounded concern (database, cache, web routing,
billing, etc.) and wires its own object graph into the shared DI container.

**Feature Provider Pattern**
-----------------------------

A *feature provider* packages all services for a vertical slice (bounded
context) of your domain into a single, self-contained unit.  This keeps
module boundaries explicit and makes it easy to enable or disable features
by adding or removing a provider.

Typical structure::

    # my_app/billing/di/provider.py

    from quadkit.di.provider import Provider
    from quadkit.contracts.core import ProviderPriority
    from quadkit.contracts.core.di import ContainerRegistrarProtocol, ContainerResolverProtocol

    from my_app.billing.config import BillingConfig
    from my_app.billing.services import PaymentService, InvoiceService
    from my_app.billing.repos import InvoiceRepository
    from my_app.billing.ports import PaymentGateway
    from my_app.billing.adapters.stripe import StripeGateway

    class BillingProvider(Provider):
        name = "billing"
        priority = ProviderPriority.APPLICATION

        async def register(self, container: ContainerRegistrarProtocol) -> None:
            cfg = BillingConfig()

            # Bind the contract/protocol — never the concrete adapter directly
            container.singleton(PaymentGateway, StripeGateway(cfg.stripe_key))
            container.singleton(InvoiceRepository, InvoiceRepository(cfg.db_url))

        async def boot(self, container: BootContainerProtocol) -> None:
            # Wire services that depend on already-registered bindings
            gateway = await container.resolve(PaymentGateway)
            repo = await container.resolve(InvoiceRepository)
            container.singleton(PaymentService, PaymentService(gateway, repo))
            container.singleton(InvoiceService, InvoiceService(repo))

Register the provider once in the composition root::

    app = Application()
    app.add_provider(BillingProvider())

Cross-extension communication always goes through the contracts layer:
never import from another extension package directly.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any, Self

from quadkit.contracts.core import ProviderPriority

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )
    from quadkit.contracts.core.health import HealthCheckResult


class ProviderState(enum.StrEnum):
    """Provider lifecycle state."""

    CREATED = "created"
    REGISTERED = "registered"
    BOOTED = "booted"
    SHUTDOWN = "shutdown"


class Provider:
    """Base class for all Quadkit providers.

    Providers are part of the composition root. They register
    bindings and wire the object graph during boot.

    """

    name: str = ""
    priority: ProviderPriority = ProviderPriority.NORMAL
    dependencies: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()
    boot_timeout: float | None = None
    required: bool = True
    config_key: str | None = None
    config_model: type[Any] | None = None

    def __init__(
        self,
        name: str | None = None,
        priority: ProviderPriority | None = None,
        dependencies: tuple[str, ...] | None = None,
        optional_dependencies: tuple[str, ...] | None = None,
        boot_timeout: float | None = None,
        required: bool | None = None,
    ) -> None:
        if name is not None:
            self.name = name
        if priority is not None:
            self.priority = priority
        if dependencies is not None:
            self.dependencies = dependencies
        if optional_dependencies is not None:
            self.optional_dependencies = optional_dependencies
        if boot_timeout is not None:
            self.boot_timeout = boot_timeout
        if required is not None:
            self.required = required

        if not self.name:
            cls_name = type(self).__name__
            self.name = cls_name.removesuffix("Provider").lower() or cls_name.lower()

        self._state = ProviderState.CREATED
        self._config: Any = None
        self._config_from_factory: bool = False

    @property
    def state(self) -> ProviderState:
        return self._state

    @property
    def is_booted(self) -> bool:
        return self._state == ProviderState.BOOTED

    def reset_state(self) -> None:
        """Reset the lifecycle state so this provider can be booted again.

        Intended for test harnesses that restart an application while
        reusing the same provider instances (e.g.
        ``TestEnvironment.setup()`` after incremental provider
        registration).

        Note:
            Only the lifecycle state is reset; configuration and already
            registered services are left untouched.
        """
        self._state = ProviderState.CREATED

    @property
    def config(self) -> Any:
        return self._config

    @config.setter
    def config(self, value: Any) -> None:
        """Allow providers to assign configuration during initialization."""
        self._config = value

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name={self.name!r}, priority={self.priority.name}, "
            f"dependencies={self.dependencies}, "
            f"optional_dependencies={self.optional_dependencies}, "
            f"required={self.required})"
        )

    # -- Factory ----------------------------------------------------------

    @classmethod
    def from_config(cls, config: Any, **context: Any) -> Self:
        """Create a provider instance from a typed config object.

        Subclasses should implement ``from_config(cls, config: TypedConfig,
        **context: Any) -> Self`` with the exact typed config model.

        Args:
            config: Provider-specific configuration object.
            **context: Optional extra keyword arguments (e.g. pre-built
                dependencies such as a queue or store instance).

        Returns:
            A new provider instance configured from *config*.
        """
        instance = cls()
        instance._config = config
        instance._config_from_factory = True
        return instance

    # -- Lifecycle hooks (override these) ----------------------------------

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind services into the container."""

    async def boot(self, container: BootContainerProtocol) -> None:
        """Initialize services and wire dependencies."""

    async def shutdown(self) -> None:
        """Tear down resources."""

    async def on_error(self, error: Exception, phase: str) -> None:
        """Called when boot() or shutdown() raises an exception.

        Override to perform cleanup on startup/shutdown failure. This hook
        allows providers to clean up partial state when lifecycle methods fail.

        The default implementation logs the error and does not re-raise.

        Args:
            error: The exception that was raised.
            phase: Either 'boot' or 'shutdown' indicating which phase failed.
        """
        from quadkit.logging import get_logger

        logger = get_logger(__name__)
        logger.error(
            "provider_lifecycle_error",
            provider=self.name,
            phase=phase,
            error=str(error),
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return health status of this provider."""
        from quadkit.contracts.core.health import HealthCheckResult, HealthStatus

        return HealthCheckResult(component=self.name, status=HealthStatus.HEALTHY)


__all__ = ["Provider", "ProviderPriority", "ProviderState"]
