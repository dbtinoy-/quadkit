"""Convention followed: **Provider pattern** — ``register()`` declares singletons, ``boot()`` resolves contracts, ``health_check()`` reports readiness.

Lifecycle wiring for the Artifact Vault showcase."""

from __future__ import annotations

from typing import TYPE_CHECKING

from artifact_vault.config import ArtifactVaultConfig
from artifact_vault.controllers.api import ArtifactVaultApiController
from artifact_vault.services.vault import ArtifactVaultService
from quadkit.contracts import BlobStoreProtocol
from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)
from quadkit.di.provider import Provider

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


class ArtifactVaultProvider(Provider):
    """Resolve the package-owned blob store and seed one browser artifact."""

    name = "artifact_vault"
    config_key: str | None = "artifact_vault"
    config_model: type | None = ArtifactVaultConfig

    def __init__(self) -> None:
        super().__init__()
        self._service: ArtifactVaultService | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind the artifact-vault config and API controller to the container."""
        cfg = self.config or ArtifactVaultConfig()
        container.singleton(ArtifactVaultConfig, instance=cfg)
        container.singleton(ArtifactVaultApiController, ArtifactVaultApiController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Resolve dependencies, seed the store, and wire the vault service."""
        store = await container.resolve(BlobStoreProtocol)
        config = await container.resolve(ArtifactVaultConfig)
        service = ArtifactVaultService(store, config)
        await service.seed()
        self._service = service
        container.bind(
            ArtifactVaultApiController, ArtifactVaultApiController(service=service)
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return readiness status by delegating to the vault service."""
        if self._service is None:
            return HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                category=HealthCheckCategory.READINESS,
            )
        health = await self._service.health()
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus(health["status"]),
            category=HealthCheckCategory.READINESS,
            details=health["details"],
        )


__all__ = ["ArtifactVaultProvider"]
