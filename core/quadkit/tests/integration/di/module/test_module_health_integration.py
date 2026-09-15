"""Integration tests for the module health provider system.

Tests ``ProviderOrchestrator.get_module_health_providers()`` end-to-end
using a real ``Application`` boot cycle and compiled module graph.

Scenarios covered:
- ``health_providers=None``  → all module providers returned
- ``health_providers=[]``    → empty list (always healthy)
- ``health_providers=[Class]`` → matched by provider class
- ``health_providers=["name"]`` → matched by provider name string
- Called before boot → ``RuntimeError``
- ``ModuleNode.health_providers`` set correctly in compiled graph
"""

from __future__ import annotations

import pytest

from quadkit.app.base import Application
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.container import Container
from quadkit.di.module import DynamicModule, Module, module
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider

# ---------------------------------------------------------------------------
# Reusable provider stubs
# ---------------------------------------------------------------------------


class _ProviderAlpha(Provider):
    name = "provider_alpha"
    priority = ProviderPriority.APPLICATION

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass

    async def boot(self, container: ContainerResolverProtocol) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _ProviderBeta(Provider):
    name = "provider_beta"
    priority = ProviderPriority.APPLICATION

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass

    async def boot(self, container: ContainerResolverProtocol) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class _ProviderNamed(Provider):
    name = "my_named_provider"
    priority = ProviderPriority.APPLICATION

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass

    async def boot(self, container: ContainerResolverProtocol) -> None:
        pass

    async def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Module definitions (unique per test to avoid state sharing)
# ---------------------------------------------------------------------------


@module()
class _AllProvidersModule(Module):
    """health_providers=None → all providers are health providers."""

    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[_ProviderAlpha(), _ProviderBeta()],
            exports=[],
            health_providers=None,
        )


@module()
class _EmptyHealthModule(Module):
    """health_providers=[] → no providers contribute to health."""

    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[_ProviderAlpha()],
            exports=[],
            health_providers=[],
        )


@module()
class _SpecificByClassModule(Module):
    """health_providers=[_ProviderAlpha] → only alpha contributes."""

    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[_ProviderAlpha(), _ProviderBeta()],
            exports=[],
            health_providers=[_ProviderAlpha],
        )


@module()
class _SpecificByNameModule(Module):
    """health_providers=['my_named_provider'] → matched by name string."""

    @classmethod
    def configure(cls) -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[_ProviderAlpha(), _ProviderNamed()],
            exports=[],
            health_providers=["my_named_provider"],
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestModuleHealthProviders:
    """Integration tests for ProviderOrchestrator.get_module_health_providers."""

    @pytest.mark.asyncio
    async def test_health_providers_none_returns_all_providers(self) -> None:
        """health_providers=None means every module provider is a health provider."""
        async with Application.boot(modules=[_AllProvidersModule.configure()]) as app:
            providers = app._orchestrator.get_module_health_providers(
                _AllProvidersModule
            )

        assert len(providers) == 2
        provider_types = {type(p) for p in providers}
        assert _ProviderAlpha in provider_types
        assert _ProviderBeta in provider_types

    @pytest.mark.asyncio
    async def test_health_providers_empty_returns_none(self) -> None:
        """health_providers=[] means the module is always considered healthy."""
        async with Application.boot(modules=[_EmptyHealthModule.configure()]) as app:
            providers = app._orchestrator.get_module_health_providers(
                _EmptyHealthModule
            )

        assert providers == []

    @pytest.mark.asyncio
    async def test_health_providers_specific_by_class(self) -> None:
        """health_providers=[ProviderClass] returns only that provider instance."""
        async with Application.boot(
            modules=[_SpecificByClassModule.configure()]
        ) as app:
            providers = app._orchestrator.get_module_health_providers(
                _SpecificByClassModule
            )

        assert len(providers) == 1
        assert isinstance(providers[0], _ProviderAlpha)

    @pytest.mark.asyncio
    async def test_health_providers_specific_by_name_string(self) -> None:
        """health_providers=['name'] returns the provider instance with that name."""
        async with Application.boot(modules=[_SpecificByNameModule.configure()]) as app:
            providers = app._orchestrator.get_module_health_providers(
                _SpecificByNameModule
            )

        assert len(providers) == 1
        assert isinstance(providers[0], _ProviderNamed)
        assert providers[0].name == "my_named_provider"

    @pytest.mark.asyncio
    async def test_raises_before_boot(self) -> None:
        """get_module_health_providers raises RuntimeError before boot."""
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        with pytest.raises(RuntimeError, match="not been booted"):
            orchestrator.get_module_health_providers(_AllProvidersModule)

    @pytest.mark.asyncio
    async def test_health_graph_node_has_correct_health_providers(self) -> None:
        """ModuleNode.health_providers in the compiled graph matches the DynamicModule declaration."""
        async with Application.boot(
            modules=[_SpecificByClassModule.configure()]
        ) as app:
            graph = app._orchestrator._compiled_graph
            assert graph is not None
            node = graph.nodes.get(_SpecificByClassModule)

        assert node is not None
        assert node.health_providers == [_ProviderAlpha]
