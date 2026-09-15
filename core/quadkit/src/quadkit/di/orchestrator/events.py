"""Lifecycle event emitter for provider hook dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from quadkit.contracts.core.lifecycle import (
    OnApplicationBootstrapProtocol,
    OnApplicationShutdownProtocol,
    OnBeforeShutdownProtocol,
    OnModuleInitProtocol,
)
from quadkit.di.module.base import Module
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.orchestrator.registry import ProviderRegistry
    from quadkit.di.provider import Provider

logger = get_logger(__name__)


class LifecycleEventEmitter:
    """Emits lifecycle events to provider hooks.

    Dispatches framework lifecycle protocols to all registered providers that
    implement them. Also handles module-level booted/shutdown hooks using the
    compiled module graph.
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        """Initialize with a provider registry.

        Args:
            registry: The provider registry to source providers from.
        """
        self._registry = registry

    async def _call_lifecycle_hooks(
        self,
        protocol: type,
        method_name: str,
        log_key: str,
    ) -> None:
        """Call a lifecycle hook method on all providers implementing the protocol.

        Args:
            protocol: The protocol class to check against.
            method_name: The method to call on matching providers.
            log_key: Structured log key for debug/warning messages.
        """
        for provider in self._registry._providers.values():
            if isinstance(provider, protocol):
                provider_name = getattr(provider, "name", type(provider).__name__)
                try:
                    method = getattr(provider, method_name)
                    await method()
                    logger.debug(log_key, provider=provider_name)
                except (RuntimeError, OSError, AttributeError, ValueError) as e:
                    logger.warning(
                        "%s.failed",
                        log_key,
                        provider=provider_name,
                        error=str(e),
                    )

    async def emit_application_bootstrap(self) -> None:
        """Emit OnApplicationBootstrapProtocol to all registered providers."""
        await self._call_lifecycle_hooks(
            OnApplicationBootstrapProtocol,
            "on_application_bootstrap",
            "lifecycle.app_bootstrap",
        )

    async def emit_before_shutdown(self) -> None:
        """Emit OnBeforeShutdownProtocol to all registered providers."""
        await self._call_lifecycle_hooks(
            OnBeforeShutdownProtocol,
            "on_before_shutdown",
            "lifecycle.before_shutdown",
        )

    async def emit_application_shutdown(self) -> None:
        """Emit OnApplicationShutdownProtocol to all registered providers."""
        await self._call_lifecycle_hooks(
            OnApplicationShutdownProtocol,
            "on_application_shutdown",
            "lifecycle.app_shutdown",
        )

    async def emit_module_init(self, provider: Provider) -> None:
        """Emit OnModuleInitProtocol for a single provider if it implements it.

        Args:
            provider: The provider to emit the module init event for.
        """
        if isinstance(provider, OnModuleInitProtocol):
            provider_name = getattr(provider, "name", type(provider).__name__)
            try:
                await provider.on_module_init()
                logger.debug("lifecycle.module_init", provider=provider_name)
            except (RuntimeError, OSError, AttributeError, ValueError) as e:
                logger.warning(
                    "lifecycle.module_init.failed",
                    provider=provider_name,
                    error=str(e),
                )

    async def emit_module_booted(self) -> None:
        """Call on_module_booted() for all modules after their providers boot.

        Only fires when a compiled graph is available (module context exists).
        Hook errors are logged but do not fail the boot process.
        """
        compiled_graph = self._registry._compiled_graph
        if compiled_graph is None:
            return

        for module_class in compiled_graph.nodes:
            hook = getattr(module_class, "on_module_booted", None)
            if hook is None:
                continue
            try:
                await cast("type[Module]", module_class).on_module_booted()
                logger.debug(
                    "lifecycle.on_module_booted",
                    module=module_class.__name__,
                )
            except (RuntimeError, OSError, AttributeError, ValueError, TypeError) as e:
                logger.warning(
                    "lifecycle.on_module_booted.error",
                    module=module_class.__name__,
                    error_type=type(e).__name__,
                    error=str(e),
                )

    async def emit_module_shutdown(self) -> None:
        """Call on_module_shutdown() for all modules before providers shut down.

        Only fires when a compiled graph is available. Modules are shut down in
        reverse topological order (most dependent first).
        Hook errors are logged but do not prevent shutdown.
        """
        compiled_graph = self._registry._compiled_graph
        if compiled_graph is None:
            return

        module_order = list(reversed(list(compiled_graph.nodes.keys())))

        for module_class in module_order:
            hook = getattr(module_class, "on_module_shutdown", None)
            if hook is None:
                continue
            try:
                await cast("type[Module]", module_class).on_module_shutdown()
                logger.debug(
                    "lifecycle.on_module_shutdown",
                    module=module_class.__name__,
                )
            except (RuntimeError, OSError, AttributeError, ValueError, TypeError) as e:
                logger.warning(
                    "lifecycle.on_module_shutdown.error",
                    module=module_class.__name__,
                    error_type=type(e).__name__,
                    error=str(e),
                )


__all__ = ["LifecycleEventEmitter"]
