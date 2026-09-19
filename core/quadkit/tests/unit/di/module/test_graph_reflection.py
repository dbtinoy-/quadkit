"""Tests for typed reflection methods on CompiledModuleGraph."""

from __future__ import annotations

from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.module import CompiledModuleGraph, ModuleCompiler, module
from quadkit.di.provider import Provider, ProviderPriority

# ---------------------------------------------------------------------------
# Minimal provider stubs
# ---------------------------------------------------------------------------


class _ProvA(Provider):
    name = "prov_a"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class _ProvB(Provider):
    name = "prov_b"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class _ProvC(Provider):
    name = "prov_c"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


# ---------------------------------------------------------------------------
# Fake service types used as exports
# ---------------------------------------------------------------------------


class _ServiceA:
    pass


class _ServiceB:
    pass


class _ServiceC:
    pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _compile(*root_modules: type) -> CompiledModuleGraph:
    """Compile a graph from the given root module classes."""
    return ModuleCompiler().compile(root_modules=list(root_modules))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetModuleByName:
    def test_found(self) -> None:
        @module(providers=[_ProvA])
        class UserModule:
            pass

        graph = _compile(UserModule)
        result = graph.get_module_by_name("UserModule")
        assert result is UserModule

    def test_not_found(self) -> None:
        @module(providers=[_ProvA])
        class AnotherModule:
            pass

        graph = _compile(AnotherModule)
        assert graph.get_module_by_name("NonExistentModule") is None


class TestGetExportsForModule:
    def test_returns_exports(self) -> None:
        @module(providers=[_ProvA], exports=[_ServiceA, _ServiceB])
        class ExportingModule:
            pass

        graph = _compile(ExportingModule)
        exports = graph.get_exports_for_module(ExportingModule)
        assert _ServiceA in exports
        assert _ServiceB in exports

    def test_unknown_module_returns_empty_frozenset(self) -> None:
        @module(providers=[_ProvA])
        class SomeModule:
            pass

        class UnknownModule:
            pass

        graph = _compile(SomeModule)
        assert graph.get_exports_for_module(UnknownModule) == frozenset()

    def test_returns_frozenset_type(self) -> None:
        @module(providers=[_ProvA], exports=[_ServiceA])
        class TypedExportModule:
            pass

        graph = _compile(TypedExportModule)
        result = graph.get_exports_for_module(TypedExportModule)
        assert isinstance(result, frozenset)


class TestGetImportingModules:
    def test_single_importer(self) -> None:
        @module(providers=[_ProvA], exports=[_ServiceA])
        class BaseModule:
            pass

        @module(imports=[BaseModule], providers=[_ProvB])
        class ConsumerModule:
            pass

        graph = _compile(ConsumerModule)
        importers = graph.get_importing_modules(BaseModule)
        assert ConsumerModule in importers

    def test_multiple_importers(self) -> None:
        @module(providers=[_ProvA], exports=[_ServiceA])
        class SharedModule:
            pass

        @module(imports=[SharedModule], providers=[_ProvB])
        class ConsumerOne:
            pass

        @module(imports=[SharedModule], providers=[_ProvC])
        class ConsumerTwo:
            pass

        graph = _compile(ConsumerOne, ConsumerTwo)
        importers = graph.get_importing_modules(SharedModule)
        assert ConsumerOne in importers
        assert ConsumerTwo in importers

    def test_no_importers_returns_empty(self) -> None:
        @module(providers=[_ProvA])
        class StandaloneModule:
            pass

        graph = _compile(StandaloneModule)
        assert graph.get_importing_modules(StandaloneModule) == frozenset()


class TestGetDependencyChain:
    def test_bfs_order(self) -> None:
        @module(providers=[_ProvA], exports=[_ServiceA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[_ProvB], exports=[_ServiceB])
        class ModB:
            pass

        @module(imports=[ModB], providers=[_ProvC])
        class ModC:
            pass

        graph = _compile(ModC)
        chain = graph.get_dependency_chain(ModC)

        # ModB is a direct import of ModC; ModA is a transitive import via ModB
        assert ModB in chain
        assert ModA in chain
        assert chain.index(ModB) < chain.index(ModA)

    def test_root_not_included(self) -> None:
        @module(providers=[_ProvA], exports=[_ServiceA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[_ProvB])
        class ModB:
            pass

        graph = _compile(ModB)
        chain = graph.get_dependency_chain(ModB)
        assert ModB not in chain

    def test_empty_for_unknown_module(self) -> None:
        @module(providers=[_ProvA])
        class KnownModule:
            pass

        class UnknownModule:
            pass

        graph = _compile(KnownModule)
        assert graph.get_dependency_chain(UnknownModule) == []

    def test_no_imports_returns_empty(self) -> None:
        @module(providers=[_ProvA])
        class LeafModule:
            pass

        graph = _compile(LeafModule)
        assert graph.get_dependency_chain(LeafModule) == []


class TestGetBootLevel:
    def test_found(self) -> None:
        @module(providers=[_ProvA])
        class BootModule:
            pass

        graph = _compile(BootModule)
        level = graph.get_boot_level(BootModule)
        assert isinstance(level, int)

    def test_not_found_returns_none(self) -> None:
        @module(providers=[_ProvA])
        class SomeModule:
            pass

        class NotInGraph:
            pass

        graph = _compile(SomeModule)
        assert graph.get_boot_level(NotInGraph) is None

    def test_get_boot_level_module_with_no_providers_returns_none(self) -> None:
        # A module that is in the graph but has no providers gets None
        @module(providers=[_ProvA], exports=[_ServiceA])
        class ModuleWithProviders:
            pass

        @module(imports=[ModuleWithProviders])
        class ModuleWithoutProviders:
            pass

        graph = _compile(ModuleWithoutProviders)
        # ModuleWithoutProviders is in the graph but has no providers
        assert graph.get_boot_level(ModuleWithoutProviders) is None
        # ModuleWithProviders has providers and should have a boot level
        assert graph.get_boot_level(ModuleWithProviders) is not None

    def test_imported_module_boots_before_importer(self) -> None:
        @module(providers=[_ProvA], exports=[_ServiceA])
        class EarlyModule:
            pass

        @module(imports=[EarlyModule], providers=[_ProvB])
        class LateModule:
            pass

        graph = _compile(LateModule)
        early_level = graph.get_boot_level(EarlyModule)
        late_level = graph.get_boot_level(LateModule)

        assert early_level is not None
        assert late_level is not None
        assert early_level <= late_level
