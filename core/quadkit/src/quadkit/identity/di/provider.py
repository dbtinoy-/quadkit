"""DI provider for the core identity subsystem."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.contracts.core.identity import IdGeneratorProtocol, IdStrategy
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.identity.config import IdentityConfig
from quadkit.identity.generator import (
    PrefixedIdGenerator,
    UlidGenerator,
    Uuid4Generator,
    Uuid7Generator,
)

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )


class IdentityProvider(Provider):
    """Register identity generators for the framework."""

    name = "identity"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(self, config: IdentityConfig | None = None) -> None:
        super().__init__()
        self._config = config or IdentityConfig()
        self._generator: IdGeneratorProtocol | None = None

    def _build_generator(self) -> IdGeneratorProtocol:
        strategy = self._config.strategy
        if strategy == IdStrategy.UUID7:
            return Uuid7Generator()
        if strategy == IdStrategy.ULID:
            return UlidGenerator()
        if strategy == IdStrategy.PREFIXED:
            return PrefixedIdGenerator(
                prefix_map=self._config.prefix_map,
                separator=self._config.prefix_separator,
            )
        return Uuid4Generator()

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register the active generator implementation."""
        self._generator = self._build_generator()
        container.singleton(IdentityConfig, instance=self._config)
        container.singleton(self._generator.__class__, instance=self._generator)
        container.singleton(IdGeneratorProtocol, instance=self._generator)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Install the resolved generator into ambient."""
        generator = await container.resolve(IdGeneratorProtocol)

        from quadkit.identity import ambient as identity_ambient

        identity_ambient.install(generator)

    async def shutdown(self) -> None:
        """Identity services do not require shutdown work."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report the identity subsystem as healthy."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"strategy": self._config.strategy.value},
        )


__all__ = ["IdentityProvider"]
