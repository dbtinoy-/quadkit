"""Boot-time engine that registers enabled entry-point providers.

Consumed by :class:`PluginsModule`. Discovery, filtering, and instantiation
are delegated to the shared ``discover_providers`` primitive
(``quadkit.plugins.discovery``); this engine drives container registration
and the ``boot()``/``shutdown()`` lifecycle of the discovered providers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from quadkit.di.provider import Provider, ProviderPriority
from quadkit.logging import get_logger
from quadkit.plugins.discovery import (
    discover_plugins,
    discover_providers,
    validate_plan,
)
from quadkit.plugins.state import load_disabled

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )

logger = get_logger(__name__)

__all__ = ["PluginEngineProvider"]


class PluginEngineProvider(Provider):
    """Register every enabled entry-point provider declared by a plugin.

    During ``register()`` the provider loads the plugin-state ``disabled``
    set and delegates discovery, filtering, and instantiation to the shared
    ``discover_providers()`` primitive — the single implementation of the
    entry-point discover→filter→load→instantiate path. It then registers
    each provider with the container and tracks it for lifecycle so plugin
    providers participate in the application lifecycle without belonging to
    the orchestrator's static list. Framework packages that register under
    ``EP_PROVIDERS`` (admin, auth, sql, web, ...) are *not* plugins and are
    never auto-registered; they are composed explicitly by the application's
    module graph.

    Attributes:
        discovered_providers: Providers instantiated during ``register()``,
            used for lifecycle and by tests.
    """

    name = "plugins"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(self, state_path: str | Path | None = None) -> None:
        super().__init__()
        self._state_path = state_path
        self.discovered_providers: list[Provider] = []

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Discover and register enabled plugin providers, skipping the disabled set.

        ``validate_plan`` enforces descriptor ``requires``/``conflicts``
        (advisory): plugins whose dependencies are missing or whose conflicts
        are enabled are excluded from registration with a logged warning —
        never raised, and boot is never blocked.

        Args:
            container: The DI container registrar.
        """
        descriptors = discover_plugins()
        if not descriptors:
            logger.debug("plugins.engine.no_plugin_descriptors")
            return
        disabled = load_disabled(self._state_path)
        if disabled:
            logger.info(
                "plugins.engine.disabled_at_boot",
                disabled=sorted(disabled),
            )
        plan = validate_plan(descriptors, disabled)
        installed = {d.provider_entry_point for d in descriptors}
        excluded = plan.disabled | (installed - plan.enabled)
        for issue in plan.issues:
            logger.warning("plugins.engine.plan_issue", issue=issue)
        for provider in discover_providers(disabled=set(excluded)):
            try:
                await provider.register(container)
            except Exception as exc:  # noqa: BLE001 — third-party provider can raise anything
                logger.warning(
                    "plugins.engine.register_failed",
                    name=provider.name,
                    error=str(exc),
                )
                continue
            self.discovered_providers.append(provider)
            logger.debug("plugins.engine.registered", name=provider.name)

    async def boot(self, container: BootContainerProtocol) -> None:
        """Boot all discovered providers.

        Args:
            container: The DI container for boot phase.
        """
        for provider in self.discovered_providers:
            await provider.boot(container)

    async def shutdown(self) -> None:
        """Shut down discovered providers in reverse discovery order."""
        for provider in reversed(self.discovered_providers):
            await provider.shutdown()
