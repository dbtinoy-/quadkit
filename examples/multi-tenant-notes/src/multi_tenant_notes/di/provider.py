"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons (including the controller, as a class binding), ``boot()``
builds the wired controller instance and rebinds it, ``health_check()``
reports readiness; ``config_key``/``config_model`` wire the typed yaml
section into ``self.config``.

Lifecycle wiring for the Multi-Tenant Notes demo.
"""

from __future__ import annotations

from multi_tenant_notes.config import MultiTenantNotesConfig
from multi_tenant_notes.controllers.api import NotesController
from multi_tenant_notes.services.notes import NotesStore
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.provider import Provider


class MultiTenantNotesProvider(Provider):
    """Bind the tenant-partitioned store and the controller."""

    name = "multi_tenant_notes"
    config_key: str | None = "multi_tenant_notes"
    config_model: type | None = MultiTenantNotesConfig

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config
            if isinstance(self.config, MultiTenantNotesConfig)
            else MultiTenantNotesConfig()
        )
        container.singleton(MultiTenantNotesConfig, config)
        container.singleton(
            NotesStore, instance=NotesStore(config.max_notes_per_tenant)
        )
        container.singleton(NotesController, NotesController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        store = await container.resolve(NotesStore)
        container.bind(NotesController, NotesController(store))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={
                "demo": "multi-tenant-notes",
                "tenant_isolation": "by-construction",
            },
        )


__all__ = ["MultiTenantNotesProvider"]
