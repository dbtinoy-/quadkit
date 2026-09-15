# file: tests/di/module/test_compiler.py
"""Tests for ModuleCompiler — graph compilation, cycle detection, validation."""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions.provider import (
    ModuleCycleError,
    ModuleDuplicateError,
    ModuleError,
    ModuleImportError,
)
from quadkit.di.module import (
    DynamicModule,
    ModuleCompiler,
    module,
)
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.provider import Provider, ProviderPriority


class ProtoA:
    """Fake protocol for testing exports."""


class ProtoB:
    """Fake protocol for testing exports."""


class ProtoC:
    """Fake protocol for testing exports."""


class StubProviderA(Provider):
    name = "stub_a"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class StubProviderB(Provider):
    name = "stub_b"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class StubProviderC(Provider):
    name = "stub_c"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        pass


class TestBasicCompilation:
    """Test simple module graph compilation."""

    def test_single_module(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        assert len(graph.nodes) == 1
        assert MyModule in graph.nodes
        assert len(graph.provider_order) == 1
        assert graph.provider_order[0].module_class is MyModule

    def test_two_independent_modules(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA, ModB])

        assert len(graph.nodes) == 2
        assert len(graph.provider_order) == 2

    def test_module_with_import(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModB])

        assert len(graph.nodes) == 2
        # ModA's providers should come before ModB's
        names = [
            type(e.provider).__name__ if e.is_instance else e.provider.__name__
            for e in graph.provider_order
        ]
        assert names.index("StubProviderA") < names.index("StubProviderB")

    def test_deep_import_chain(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC])
        class ModC:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModC])

        assert len(graph.nodes) == 3
        module_order = [e.module_name for e in graph.provider_order]
        assert module_order.index("ModA") < module_order.index("ModB")
        assert module_order.index("ModB") < module_order.index("ModC")

    def test_transitive_import(self):
        """ModC imports ModB which imports ModA — ModA should be in graph."""

        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC])
        class ModC:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModC])

        assert ModA in graph.nodes
        assert ModB in graph.nodes
        assert ModC in graph.nodes


class TestDynamicModuleCompilation:
    """Test compilation with DynamicModule entries."""

    def test_dynamic_module_replaces_static(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        dynamic = DynamicModule(
            module=MyModule,
            providers=[StubProviderB],
            exports=[ProtoB],
            is_global=True,
        )

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[dynamic])

        node = graph.nodes[MyModule]
        assert node.is_dynamic is True
        assert node.is_global is True
        assert ProtoB in node.exports

    def test_dynamic_with_instance_providers(self):
        @module()
        class MyModule:
            pass

        instance = StubProviderA()
        dynamic = DynamicModule(
            module=MyModule,
            providers=[instance],
        )

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[dynamic])

        entry = graph.provider_order[0]
        assert entry.is_instance is True
        assert entry.provider is instance

    def test_dynamic_import_resolution(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module()
        class ModB:
            pass

        dm_b = DynamicModule(
            module=ModB,
            imports=[ModA],
            providers=[StubProviderB],
        )

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[dm_b])

        assert ModA in graph.nodes
        assert ModB in graph.nodes

    def test_duplicate_dynamic_same_instance_ok(self):
        @module()
        class MyModule:
            pass

        dm = DynamicModule(module=MyModule, providers=[StubProviderA])

        compiler = ModuleCompiler()
        # Same DynamicModule instance twice — should deduplicate
        graph = compiler.compile(root_modules=[dm, dm])
        assert len(graph.nodes) == 1

    def test_duplicate_dynamic_different_config_raises(self):
        @module()
        class MyModule:
            pass

        dm1 = DynamicModule(module=MyModule, providers=[StubProviderA])
        dm2 = DynamicModule(module=MyModule, providers=[StubProviderB])

        compiler = ModuleCompiler()
        with pytest.raises(ModuleDuplicateError, match="different configurations"):
            compiler.compile(root_modules=[dm1, dm2])

    def test_duplicate_dynamic_error_includes_hint(self):
        @module()
        class MyModule:
            pass

        dm1 = DynamicModule(module=MyModule, providers=[StubProviderA])
        dm2 = DynamicModule(module=MyModule, providers=[StubProviderB])

        compiler = ModuleCompiler()
        with pytest.raises(ModuleDuplicateError) as exc_info:
            compiler.compile(root_modules=[dm1, dm2])

        exc = exc_info.value
        assert exc.hint is not None
        assert "configure() call" in exc.hint
        assert "Reference:" in exc.message


class TestCycleDetection:
    """Test circular dependency detection."""

    def test_direct_cycle(self):
        """A imports B, B imports A."""

        # We need to create these carefully to avoid Python import issues
        @module(providers=[StubProviderA])
        class ModA:
            pass

        @module(providers=[StubProviderB])
        class ModB:
            pass

        # Manually patch imports to create cycle
        ModA.__quadkit_module__ = ModA.__quadkit_module__.__class__(
            name="ModA",
            providers=(StubProviderA,),
            imports=(ModB,),
        )
        ModB.__quadkit_module__ = ModB.__quadkit_module__.__class__(
            name="ModB",
            providers=(StubProviderB,),
            imports=(ModA,),
        )

        compiler = ModuleCompiler()
        with pytest.raises(ModuleCycleError, match="Circular"):
            compiler.compile(root_modules=[ModA])

    def test_indirect_cycle(self):
        """A → B → C → A."""

        @module(providers=[StubProviderA])
        class ModA:
            pass

        @module(providers=[StubProviderB])
        class ModB:
            pass

        @module(providers=[StubProviderC])
        class ModC:
            pass

        from quadkit.di.module.metadata import ModuleMetadata

        ModA.__quadkit_module__ = ModuleMetadata(
            name="ModA",
            providers=(StubProviderA,),
            imports=(ModB,),
        )
        ModB.__quadkit_module__ = ModuleMetadata(
            name="ModB",
            providers=(StubProviderB,),
            imports=(ModC,),
        )
        ModC.__quadkit_module__ = ModuleMetadata(
            name="ModC",
            providers=(StubProviderC,),
            imports=(ModA,),
        )

        compiler = ModuleCompiler()
        with pytest.raises(ModuleCycleError):
            compiler.compile(root_modules=[ModA])

    def test_no_cycle_diamond(self):
        """A → B, A → C, B → D, C → D.  Diamond, not a cycle."""

        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModD:
            pass

        @module(imports=[ModD], providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        @module(imports=[ModD], providers=[StubProviderC], exports=[ProtoC])
        class ModC:
            pass

        @module(imports=[ModB, ModC])
        class ModA:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA])
        assert len(graph.nodes) == 4


class TestImportValidation:
    """Test that missing imports are caught."""

    def test_missing_import_raises(self):
        class NotAModule:
            pass

        @module(providers=[StubProviderA])
        class ModA:
            pass

        from quadkit.di.module.metadata import ModuleMetadata

        ModA.__quadkit_module__ = ModuleMetadata(
            name="ModA",
            providers=(StubProviderA,),
            imports=(NotAModule,),
        )

        compiler = ModuleCompiler()
        with pytest.raises((ModuleImportError, ModuleError)):
            compiler.compile(root_modules=[ModA])

    def test_not_decorated_import_error_includes_actionable_hint(self):
        class NotAModule:
            pass

        @module(providers=[StubProviderA])
        class ModA:
            pass

        from quadkit.di.module.metadata import ModuleMetadata

        ModA.__quadkit_module__ = ModuleMetadata(
            name="ModA",
            providers=(StubProviderA,),
            imports=(NotAModule,),
        )

        compiler = ModuleCompiler()
        with pytest.raises(ModuleError) as exc_info:
            compiler.compile(root_modules=[ModA])

        exc = exc_info.value
        assert exc.hint is not None
        assert "@module()" in exc.hint
        assert "Reference:" in exc.message


class TestStandaloneProviders:
    """Test standalone providers in compiled graph."""

    def test_standalone_providers_at_end(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        standalone = StubProviderB()

        compiler = ModuleCompiler()
        graph = compiler.compile(
            root_modules=[MyModule],
            standalone_providers=[standalone],
        )

        assert len(graph.provider_order) == 2
        last = graph.provider_order[-1]
        assert last.module_class is None
        assert last.module_name is None
        assert last.is_instance is True

    def test_standalone_higher_boot_level(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        standalone = StubProviderB()

        compiler = ModuleCompiler()
        graph = compiler.compile(
            root_modules=[MyModule],
            standalone_providers=[standalone],
        )

        module_level = graph.provider_order[0].boot_level
        standalone_level = graph.provider_order[-1].boot_level
        assert standalone_level > module_level


class TestGraphOutput:
    """Test CompiledModuleGraph query methods."""

    def test_get_module(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        node = graph.get_module(MyModule)
        assert node is not None
        assert node.name == "MyModule"

    def test_get_module_names(self):
        @module(providers=[StubProviderA])
        class ModA:
            pass

        @module(providers=[StubProviderB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA, ModB])

        names = graph.get_module_names()
        assert "ModA" in names
        assert "ModB" in names

    def test_dump_serializable(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        dump = graph.dump()
        assert "modules" in dump
        assert "provider_order" in dump
        assert "global_exports" in dump
        assert "warnings" in dump
