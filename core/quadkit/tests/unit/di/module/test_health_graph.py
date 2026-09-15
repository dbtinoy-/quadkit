"""Tests for health provider graph functionality."""

from __future__ import annotations

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.module.base import Module
from quadkit.di.module.compiler import ModuleCompiler
from quadkit.di.module.decorator import module
from quadkit.di.module.dynamic import DynamicModule
from quadkit.di.provider import Provider


class _ProvA(Provider):
    """Test provider A."""

    name = "prov_a"
    priority = ProviderPriority.NORMAL

    async def register(self, container):
        """Register provider A."""


class _ProvB(Provider):
    """Test provider B."""

    name = "prov_b"
    priority = ProviderPriority.NORMAL

    async def register(self, container):
        """Register provider B."""


class TestGetHealthProviders:
    """Tests for CompiledModuleGraph.get_health_providers()."""

    def _make_graph(self, health_providers):
        """Create a compiled graph with specified health_providers."""

        @module(providers=[_ProvA, _ProvB])
        class MyModule(Module):
            """Test module."""

        dynamic = DynamicModule(
            module=MyModule,
            providers=[_ProvA, _ProvB],
            exports=[],
            health_providers=health_providers,
        )

        return ModuleCompiler().compile([dynamic]), MyModule

    def test_health_providers_none_returns_all(self) -> None:
        """None means all providers contribute to health."""
        graph, MyModule = self._make_graph(None)
        providers = graph.get_health_providers(MyModule)
        assert len(providers) == 2

    def test_health_providers_empty_returns_none(self) -> None:
        """Empty list means no providers contribute (always healthy)."""
        graph, MyModule = self._make_graph([])
        providers = graph.get_health_providers(MyModule)
        assert providers == []

    def test_health_providers_specific_by_class(self) -> None:
        """List of provider classes filters to only those providers."""
        graph, MyModule = self._make_graph([_ProvA])
        providers = graph.get_health_providers(MyModule)
        assert len(providers) == 1
        # Verify it's the right provider
        assert any(
            (hasattr(p.provider, "__name__") and p.provider.__name__ == "_ProvA")
            or p.provider is _ProvA
            for p in providers
        )

    def test_unknown_module_returns_empty(self) -> None:
        """Non-existent module returns empty list."""

        @module()
        class OtherModule(Module):
            """Other module."""

        graph, _ = self._make_graph(None)
        providers = graph.get_health_providers(OtherModule)
        assert providers == []

    def test_health_providers_specific_by_string(self) -> None:
        """List of provider names (strings) filters providers."""
        graph, MyModule = self._make_graph(["prov_a"])
        providers = graph.get_health_providers(MyModule)
        assert len(providers) == 1

    def test_multiple_specific_providers(self) -> None:
        """List with multiple specific providers."""

        @module(providers=[_ProvA, _ProvB])
        class MyModule(Module):
            """Test module."""

        dynamic = DynamicModule(
            module=MyModule,
            providers=[_ProvA, _ProvB],
            exports=[],
            health_providers=[_ProvA, _ProvB],
        )

        graph = ModuleCompiler().compile([dynamic])
        providers = graph.get_health_providers(MyModule)
        assert len(providers) == 2
