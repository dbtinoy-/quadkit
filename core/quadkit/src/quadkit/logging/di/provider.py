from __future__ import annotations

from quadkit.config.main import QuadkitConfig
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus
from quadkit.di.provider import Provider, ProviderPriority


class LoggingProvider(Provider):
    """Structured logging factory and helpers DI provider."""

    name = "logging"
    priority = ProviderPriority.INFRASTRUCTURE
    dependencies = ("config",)

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register logging services."""
        from quadkit.contracts.core.logging import RedactorProtocol
        from quadkit.logging import (
            LoggerFactoryImpl,
            LoggerFactoryProtocol,
            get_logger,
        )
        from quadkit.logging import LoggerProtocol as Logger
        from quadkit.logging.redaction import DelegatingRedactor

        logger_factory = LoggerFactoryImpl()
        container.singleton(LoggerFactoryProtocol, logger_factory)
        container.singleton(Logger, get_logger("quadkit"))
        container.singleton(RedactorProtocol, DelegatingRedactor())

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Apply logging configuration from QuadkitConfig."""
        from quadkit.logging.configurator import apply_config

        config = await container.resolve(QuadkitConfig)
        apply_config(config.logging, service_name=getattr(config, "app_name", None))

    async def shutdown(self) -> None:
        """No resources to release for the logging module."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Health check — always healthy (in-process only, no external backend).

        Args:
            timeout: Ignored for in-process providers.

        Returns:
            Always HEALTHY — no external backend to check.
        """
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"status": "operational"},
        )


__all__ = ["LoggingProvider"]
