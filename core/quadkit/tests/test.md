 `tests/di/module/conftest.py`

```python
# file: tests/di/module/conftest.py
"""Shared fixtures for module system tests."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.di import ContainerRegistrarImpl
from quadkit.di.module import DynamicModule, Module, module
from quadkit.di.provider import Provider, ProviderPriority


# ---------------------------------------------------------------------------
# Reusable provider stubs
# ---------------------------------------------------------------------------


class StubProviderA(Provider):
    name = "stub_a"
    priority = ProviderPriority.NORMAL
    provides = [type("ProtoA", (), {})]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass


class StubProviderB(Provider):
    name = "stub_b"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass


class StubProviderC(Provider):
    name = "stub_c"
    priority = ProviderPriority.NORMAL

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass


class StubProviderD(Provider):
    name = "stub_d"
    priority = ProviderPriority.INFRASTRUCTURE

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass


# ---------------------------------------------------------------------------
# Reusable protocol stubs
# ---------------------------------------------------------------------------


class ProtoA:
    """Fake protocol for testing exports."""


class ProtoB:
    """Fake protocol for testing exports."""


class ProtoC:
    """Fake protocol for testing exports."""


class ProtoD:
    """Fake protocol for testing exports."""


class ProtoInternal:
    """Fake protocol that should NOT be exported."""


# ---------------------------------------------------------------------------
# Reusable provider with provides
# ---------------------------------------------------------------------------


class ProviderWithProvides(Provider):
    name = "provider_with_provides"
    provides = [ProtoA, ProtoB]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass


class ProviderExportsC(Provider):
    name = "provider_exports_c"
    provides = [ProtoC]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass


class ProviderExportsD(Provider):
    name = "provider_exports_d"
    provides = [ProtoD]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass


class InternalOnlyProvider(Provider):
    name = "internal_only"
    provides = [ProtoInternal]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        pass
```

---

### File 3: `tests/di/module/test_decorator.py`

```python
# file: tests/di/module/test_decorator.py
"""Tests for @module decorator, metadata attachment, and ClassVar inheritance."""

from __future__ import annotations

import pytest

from quadkit.di.module import (
    MODULE_METADATA_ATTR,
    DynamicModule,
    Module,
    ModuleMetadata,
    create_module,
    get_module_metadata,
    global_module,
    is_module,
    module,
)
from quadkit.contracts.exceptions.provider import ModuleError
from tests.di.module.conftest import StubProviderA, StubProviderB, ProtoA, ProtoB


class TestModuleDecorator:
    """Test @module decorator attachment and metadata creation."""

    def test_bare_decorator(self):
        @module
        class MyModule:
            pass

        assert is_module(MyModule)
        meta = get_module_metadata(MyModule)
        assert meta is not None
        assert meta.name == "MyModule"
        assert meta.providers == ()
        assert meta.imports == ()
        assert meta.exports == ()
        assert meta.is_global is False

    def test_factory_decorator_with_args(self):
        @module(
            name="custom_name",
            providers=[StubProviderA],
            exports=[ProtoA],
            is_global=True,
        )
        class MyModule:
            pass

        meta = get_module_metadata(MyModule)
        assert meta.name == "custom_name"
        assert meta.providers == (StubProviderA,)
        assert meta.exports == (ProtoA,)
        assert meta.is_global is True

    def test_empty_factory_decorator(self):
        @module()
        class MyModule:
            pass

        meta = get_module_metadata(MyModule)
        assert meta.name == "MyModule"
        assert meta.providers == ()

    def test_metadata_is_frozen(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        meta = get_module_metadata(MyModule)
        with pytest.raises(AttributeError):
            meta.name = "changed"  # type: ignore[misc]

    def test_metadata_stored_as_attribute(self):
        @module()
        class MyModule:
            pass

        assert hasattr(MyModule, MODULE_METADATA_ATTR)
        assert isinstance(getattr(MyModule, MODULE_METADATA_ATTR), ModuleMetadata)

    def test_class_returned_unchanged(self):
        class Original:
            custom_attr = 42

        decorated = module(Original)
        assert decorated is Original
        assert decorated.custom_attr == 42  # type: ignore[attr-defined]


class TestGlobalModuleDecorator:
    """Test @global_module shorthand."""

    def test_global_module(self):
        @global_module
        class MyGlobal:
            pass

        meta = get_module_metadata(MyGlobal)
        assert meta is not None
        assert meta.is_global is True
        assert meta.name == "MyGlobal"

    def test_global_module_with_classvars(self):
        @global_module
        class MyGlobal(Module):
            providers = [StubProviderA]
            exports = [ProtoA]

        meta = get_module_metadata(MyGlobal)
        assert meta.is_global is True
        assert meta.providers == (StubProviderA,)
        assert meta.exports == (ProtoA,)


class TestCreateModule:
    """Test create_module convenience function."""

    def test_create_module_as_decorator(self):
        @create_module(name="Infra", providers=[StubProviderA])
        class InfraModule:
            pass

        meta = get_module_metadata(InfraModule)
        assert meta.name == "Infra"
        assert meta.providers == (StubProviderA,)


class TestClassVarInheritance:
    """Test that @module reads ClassVar defaults from Module base."""

    def test_reads_classvars_from_base(self):
        @module()
        class MyModule(Module):
            providers = [StubProviderA, StubProviderB]
            exports = [ProtoA]

        meta = get_module_metadata(MyModule)
        assert meta.providers == (StubProviderA, StubProviderB)
        assert meta.exports == (ProtoA,)

    def test_decorator_args_override_classvars(self):
        @module(exports=[ProtoB])
        class MyModule(Module):
            providers = [StubProviderA]
            exports = [ProtoA]  # This should be overridden

        meta = get_module_metadata(MyModule)
        assert meta.providers == (StubProviderA,)  # from ClassVar
        assert meta.exports == (ProtoB,)  # from decorator

    def test_intermediate_base_inheritance(self):
        class BaseInfra(Module):
            providers = [StubProviderA]

        @module()
        class FullInfra(BaseInfra):
            exports = [ProtoA]

        meta = get_module_metadata(FullInfra)
        assert meta.providers == (StubProviderA,)  # inherited
        assert meta.exports == (ProtoA,)  # own

    def test_module_base_defaults_not_inherited(self):
        """Module base class empty lists should not leak."""

        @module()
        class MyModule(Module):
            pass

        meta = get_module_metadata(MyModule)
        assert meta.providers == ()
        assert meta.imports == ()
        assert meta.exports == ()

    def test_child_not_module_without_decorator(self):
        @module(providers=[StubProviderA])
        class Parent:
            pass

        class Child(Parent):
            pass

        assert is_module(Parent)
        assert not is_module(Child)  # NOT a module — no decorator


class TestMetadataValidation:
    """Test that ModuleMetadata rejects invalid inputs."""

    def test_instance_in_providers_raises(self):
        with pytest.raises(ModuleError, match="providers.*instance"):
            @module(providers=[StubProviderA()])  # type: ignore[list-item]
            class BadModule:
                pass

    def test_non_type_in_exports_raises(self):
        with pytest.raises(ModuleError, match="exports.*expected a type"):
            @module(exports=["not_a_type"])  # type: ignore[list-item]
            class BadModule:
                pass

    def test_invalid_import_raises(self):
        with pytest.raises(ModuleError, match="imports.*expected a module"):
            @module(imports=[42])  # type: ignore[list-item]
            class BadModule:
                pass
```

---

### File 4: `tests/di/module/test_dynamic.py`

```python
# file: tests/di/module/test_dynamic.py
"""Tests for DynamicModule creation and usage."""

from __future__ import annotations

import pytest

from quadkit.di.module import DynamicModule, Module, module
from quadkit.contracts.exceptions.provider import ModuleError
from tests.di.module.conftest import StubProviderA, StubProviderB, ProtoA, ProtoB


class TestDynamicModuleCreation:
    """Test DynamicModule dataclass behavior."""

    def test_basic_creation(self):
        @module()
        class MyModule:
            pass

        dm = DynamicModule(
            module=MyModule,
            providers=[StubProviderA],
            exports=[ProtoA],
        )

        assert dm.module is MyModule
        assert dm.providers == [StubProviderA]
        assert dm.exports == [ProtoA]
        assert dm.is_global is False
        assert dm.resolved_name == "MyModule"

    def test_custom_name(self):
        @module()
        class MyModule:
            pass

        dm = DynamicModule(module=MyModule, name="CustomName")
        assert dm.resolved_name == "CustomName"

    def test_global_flag(self):
        @module()
        class MyModule:
            pass

        dm = DynamicModule(module=MyModule, is_global=True)
        assert dm.is_global is True

    def test_instance_providers(self):
        @module()
        class MyModule:
            pass

        instance = StubProviderA()
        dm = DynamicModule(
            module=MyModule,
            providers=[instance, StubProviderB],
        )
        assert dm.providers[0] is instance
        assert dm.providers[1] is StubProviderB

    def test_non_class_module_raises(self):
        with pytest.raises(ModuleError, match="must be a class"):
            DynamicModule(module="not_a_class")  # type: ignore[arg-type]

    def test_nested_dynamic_imports(self):
        @module()
        class ModA:
            pass

        @module()
        class ModB:
            pass

        dm_a = DynamicModule(module=ModA, exports=[ProtoA])
        dm_b = DynamicModule(module=ModB, imports=[dm_a], exports=[ProtoB])

        assert len(dm_b.imports) == 1
        assert dm_b.imports[0] is dm_a

    def test_repr(self):
        @module()
        class MyModule:
            pass

        dm = DynamicModule(
            module=MyModule,
            providers=[StubProviderA],
            exports=[ProtoA],
            is_global=True,
        )
        r = repr(dm)
        assert "MyModule" in r
        assert "providers=1" in r
        assert "is_global=True" in r


class TestForRootPattern:
    """Test the configure() / for_feature() factory pattern."""

    def test_for_root_returns_dynamic_module(self):
        @module()
        class DatabaseModule(Module):
            @classmethod
            def configure(cls, url: str) -> DynamicModule:
                return DynamicModule(
                    module=cls,
                    providers=[StubProviderA],
                    exports=[ProtoA],
                    is_global=True,
                )

        dm = DatabaseModule.configure("postgresql://localhost/test")
        assert isinstance(dm, DynamicModule)
        assert dm.module is DatabaseModule
        assert dm.is_global is True
        assert dm.exports == [ProtoA]

    def test_for_feature_returns_dynamic_module(self):
        @module()
        class DatabaseModule(Module):
            @classmethod
            def for_feature(cls, *models: type) -> DynamicModule:
                return DynamicModule(
                    module=cls,
                    providers=[StubProviderB],
                )

        dm = DatabaseModule.for_feature(str, int)
        assert isinstance(dm, DynamicModule)
        assert dm.module is DatabaseModule
        assert dm.is_global is False

    def test_for_root_with_instance_providers(self):
        @module()
        class CacheModule(Module):
            @classmethod
            def configure(cls, backend: str) -> DynamicModule:
                instance = StubProviderA()
                return DynamicModule(
                    module=cls,
                    providers=[instance],
                    exports=[ProtoA],
                )

        dm = CacheModule.configure("redis")
        assert len(dm.providers) == 1
        assert isinstance(dm.providers[0], StubProviderA)
```

---

### File 5: `tests/di/module/test_compiler.py`

```python
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
    CompiledModuleGraph,
    DynamicModule,
    Module,
    ModuleCompiler,
    module,
)
from tests.di.module.conftest import (
    ProtoA,
    ProtoB,
    ProtoC,
    ProtoD,
    ProviderExportsC,
    ProviderExportsD,
    ProviderWithProvides,
    StubProviderA,
    StubProviderB,
    StubProviderC,
)


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
            name="ModA", providers=(StubProviderA,), imports=(ModB,),
        )
        ModB.__quadkit_module__ = ModuleMetadata(
            name="ModB", providers=(StubProviderB,), imports=(ModC,),
        )
        ModC.__quadkit_module__ = ModuleMetadata(
            name="ModC", providers=(StubProviderC,), imports=(ModA,),
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
```

---

### File 6: `tests/di/module/test_global.py`

```python
# file: tests/di/module/test_global.py
"""Tests for global module visibility."""

from __future__ import annotations

import pytest

from quadkit.di.module import DynamicModule, ModuleCompiler, global_module, module
from tests.di.module.conftest import (
    ProtoA,
    ProtoB,
    ProtoC,
    StubProviderA,
    StubProviderB,
    StubProviderC,
)


class TestGlobalModuleVisibility:
    """Test that global module exports are visible to all modules."""

    def test_global_exports_in_visibility(self):
        @global_module
        class GlobalModule:
            providers = [StubProviderA]
            exports = [ProtoA]

        @module(providers=[StubProviderB], exports=[ProtoB])
        class OtherModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[GlobalModule, OtherModule])

        # ProtoA should be visible to OtherModule even without import
        assert graph.is_visible(OtherModule, ProtoA)

    def test_global_exports_computed(self):
        @global_module
        class GlobalModule:
            providers = [StubProviderA]
            exports = [ProtoA]

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[GlobalModule])

        assert ProtoA in graph.global_exports

    def test_non_global_not_in_global_exports(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class RegularModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[RegularModule])

        assert ProtoA not in graph.global_exports

    def test_dynamic_global_module(self):
        @module()
        class InfraModule:
            pass

        dm = DynamicModule(
            module=InfraModule,
            providers=[StubProviderA],
            exports=[ProtoA],
            is_global=True,
        )

        @module(providers=[StubProviderB])
        class AppModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[dm, AppModule])

        assert ProtoA in graph.global_exports
        assert graph.is_visible(AppModule, ProtoA)

    def test_multiple_global_modules(self):
        @global_module
        class ConfigModule:
            providers = [StubProviderA]
            exports = [ProtoA]

        @global_module
        class LoggingModule:
            providers = [StubProviderB]
            exports = [ProtoB]

        @module(providers=[StubProviderC])
        class AppModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(
            root_modules=[ConfigModule, LoggingModule, AppModule],
        )

        assert graph.is_visible(AppModule, ProtoA)
        assert graph.is_visible(AppModule, ProtoB)
        assert len(graph.global_exports) == 2
```

---

### File 7: `tests/di/module/test_reexport.py`

```python
# file: tests/di/module/test_reexport.py
"""Tests for re-export expansion."""

from __future__ import annotations

import pytest

from quadkit.di.module import ModuleCompiler, module
from tests.di.module.conftest import (
    ProtoA,
    ProtoB,
    ProtoC,
    StubProviderA,
    StubProviderB,
    StubProviderC,
)


class TestReExportExpansion:
    """Test that module classes in exports are expanded."""

    def test_reexport_expands_types(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(
            imports=[ModA],
            providers=[StubProviderB],
            exports=[ModA, ProtoB],  # Re-export ModA
        )
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModB])

        node_b = graph.nodes[ModB]
        # ModB's exports should include ProtoA (from ModA) and ProtoB
        assert ProtoA in node_b.exports
        assert ProtoB in node_b.exports

    def test_reexport_makes_types_visible_to_importers(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(
            imports=[ModA],
            providers=[StubProviderB],
            exports=[ModA, ProtoB],  # Re-export
        )
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC])
        class ModC:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModC])

        # ModC imports ModB which re-exports ModA
        # So ProtoA should be visible to ModC
        assert graph.is_visible(ModC, ProtoA)
        assert graph.is_visible(ModC, ProtoB)

    def test_reexport_chain(self):
        """A exports ProtoA, B re-exports A, C re-exports B."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB], exports=[ModA, ProtoB])
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC], exports=[ModB, ProtoC])
        class ModC:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModC])

        # ModC re-exports ModB, which re-exports ModA
        node_c = graph.nodes[ModC]
        assert ProtoA in node_c.exports
        assert ProtoB in node_c.exports
        assert ProtoC in node_c.exports
```

---

### File 8: `tests/di/module/test_visibility.py`

```python
# file: tests/di/module/test_visibility.py
"""Tests for cross-module visibility rules."""

from __future__ import annotations

import pytest

from quadkit.di.module import ModuleCompiler, module, global_module
from tests.di.module.conftest import (
    ProtoA,
    ProtoB,
    ProtoC,
    ProtoInternal,
    StubProviderA,
    StubProviderB,
    StubProviderC,
)


class TestVisibilityRules:
    """Test the 6 visibility rules from the plan."""

    def test_own_exports_visible(self):
        """Rule 1: A provider can see services from its own module."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA])

        assert graph.is_visible(ModA, ProtoA)

    def test_imported_exports_visible(self):
        """Rule 2: A provider can see exports from an imported module."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModB])

        assert graph.is_visible(ModB, ProtoA)

    def test_global_exports_visible_without_import(self):
        """Rule 3: A provider can see exports from a global module."""
        @global_module
        class GlobalMod:
            providers = [StubProviderA]
            exports = [ProtoA]

        @module(providers=[StubProviderB])
        class OtherMod:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[GlobalMod, OtherMod])

        assert graph.is_visible(OtherMod, ProtoA)

    def test_non_exported_not_visible(self):
        """Rule 4: Non-exported services from another module are NOT visible."""
        @module(
            providers=[StubProviderA],
            exports=[ProtoA],  # Only ProtoA exported
        )
        class ModA:
            pass

        @module(imports=[ModA], providers=[StubProviderB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModB])

        # ProtoA is visible (exported)
        assert graph.is_visible(ModB, ProtoA)
        # ProtoInternal is NOT visible (not exported by ModA)
        assert not graph.is_visible(ModB, ProtoInternal)

    def test_standalone_no_restriction(self):
        """Rule 5: Standalone providers (no module) have no restrictions."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA])

        # A class not in the graph — treated as standalone
        class NotAModule:
            pass

        assert graph.is_visible(NotAModule, ProtoA)
        assert graph.is_visible(NotAModule, ProtoInternal)

    def test_not_imported_not_visible(self):
        """Module that is NOT imported — its exports are not visible."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModA:
            pass

        @module(providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA, ModB])

        # ModB does not import ModA
        assert not graph.is_visible(ModB, ProtoA)
        # ModA does not import ModB
        assert not graph.is_visible(ModA, ProtoB)

    def test_transitive_import_not_visible(self):
        """A → B → C.  A should NOT see C's exports (only B's)."""
        @module(providers=[StubProviderA], exports=[ProtoA])
        class ModC:
            pass

        @module(imports=[ModC], providers=[StubProviderB], exports=[ProtoB])
        class ModB:
            pass

        @module(imports=[ModB], providers=[StubProviderC])
        class ModA:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[ModA])

        # A can see B's exports
        assert graph.is_visible(ModA, ProtoB)
        # A canNOT see C's exports (not directly imported, not re-exported)
        assert not graph.is_visible(ModA, ProtoA)
```

---

### File 9: `tests/di/module/test_registry.py`

```python
# file: tests/di/module/test_registry.py
"""Tests for ModuleRegistry — ownership tracking and export validation."""

from __future__ import annotations

import pytest

from quadkit.di.module import ModuleCompiler, ModuleRegistry, module
from tests.di.module.conftest import ProtoA, ProtoB, ProtoC, StubProviderA, StubProviderB


class TestOwnershipTracking:
    """Test service type → module ownership mapping."""

    def test_register_ownership(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule, "stub_a")

        assert registry.get_owner(ProtoA) is MyModule

    def test_standalone_ownership(self):
        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, None, "standalone_provider")

        assert registry.get_owner(ProtoA) is None

    def test_get_module_services(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule)
        registry.register_ownership(ProtoB, MyModule)

        services = registry.get_module_services(MyModule)
        assert ProtoA in services
        assert ProtoB in services

    def test_unknown_type_returns_none(self):
        registry = ModuleRegistry()
        assert registry.get_owner(ProtoA) is None

    def test_register_provider(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_provider("stub_a", MyModule)

        assert registry.get_provider_module("stub_a") is MyModule


class TestExportValidation:
    """Test post-registration export validation."""

    def test_valid_exports_pass(self):
        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule, "stub_a")

        issues = registry.validate_exports(graph)
        assert issues == []

    def test_missing_export_detected(self):
        @module(providers=[StubProviderA], exports=[ProtoA, ProtoB])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        # Only ProtoA registered, ProtoB missing
        registry.register_ownership(ProtoA, MyModule, "stub_a")

        issues = registry.validate_exports(graph)
        assert len(issues) == 1
        assert "ProtoB" in issues[0]

    def test_all_exports_missing(self):
        @module(providers=[StubProviderA], exports=[ProtoA, ProtoB])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        # Nothing registered

        issues = registry.validate_exports(graph)
        assert len(issues) == 2

    def test_no_exports_no_issues(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        issues = registry.validate_exports(graph)
        assert issues == []

    def test_container_fallback_check(self):
        """If container.has() returns True, the export is satisfied."""

        @module(providers=[StubProviderA], exports=[ProtoA])
        class MyModule:
            pass

        compiler = ModuleCompiler()
        graph = compiler.compile(root_modules=[MyModule])

        registry = ModuleRegistry()
        # ProtoA NOT tracked in registry, but container has it

        class FakeContainer:
            def has(self, t):
                return t is ProtoA

        issues = registry.validate_exports(graph, container=FakeContainer())
        assert issues == []

    def test_dump(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        registry = ModuleRegistry()
        registry.register_ownership(ProtoA, MyModule, "stub_a")
        registry.register_provider("stub_a", MyModule)

        dump = registry.dump()
        assert "modules" in dump
        assert "MyModule" in dump["modules"]
        assert "ProtoA" in dump["modules"]["MyModule"]
```

---

### File 10: `tests/di/module/test_errors.py`

```python
# file: tests/di/module/test_errors.py
"""Tests for diagnostic error message quality."""

from __future__ import annotations

import pytest

from quadkit.di.module.errors import (
    format_cycle_error,
    format_duplicate_module_error,
    format_missing_export_error,
    format_missing_import_error,
    format_not_a_module_error,
    format_visibility_error,
)


class TestCycleErrorFormat:
    def test_contains_cycle_path(self):
        msg = format_cycle_error(["A", "B", "C", "A"])
        assert "A → B → C → A" in msg

    def test_contains_fix_suggestion(self):
        msg = format_cycle_error(["X", "Y", "X"])
        assert "Break the cycle" in msg
        assert "Extract shared types" in msg


class TestMissingImportErrorFormat:
    def test_names_module_and_missing(self):
        msg = format_missing_import_error("Billing", "Payment", ["Auth", "Billing"])
        assert "Billing imports 'Payment'" in msg
        assert "Payment is not registered" in msg

    def test_lists_available_modules(self):
        msg = format_missing_import_error("X", "Y", ["A", "B", "C"])
        assert "A" in msg
        assert "B" in msg
        assert "C" in msg

    def test_contains_fix_suggestion(self):
        msg = format_missing_import_error("X", "Y", [])
        assert "To fix:" in msg
        assert "add_module" in msg


class TestMissingExportErrorFormat:
    def test_names_module_and_export(self):
        msg = format_missing_export_error(
            "Cache", "CacheBackend", ["CacheProvider"], ["CacheKey"],
        )
        assert "Cache declares export 'CacheBackend'" in msg
        assert "no provider in Cache registered" in msg

    def test_lists_providers_and_registered(self):
        msg = format_missing_export_error(
            "M", "X", ["ProvA", "ProvB"], ["TypeY", "TypeZ"],
        )
        assert "ProvA" in msg
        assert "ProvB" in msg
        assert "TypeY" in msg
        assert "TypeZ" in msg

    def test_contains_fix_suggestion(self):
        msg = format_missing_export_error("M", "X", [], [])
        assert "To fix:" in msg


class TestVisibilityErrorFormat:
    def test_names_all_parties(self):
        msg = format_visibility_error(
            "Billing", "BillingProvider", "Auth", "TokenService", ["AuthProto"],
        )
        assert "BillingProvider" in msg
        assert "Billing" in msg or "BillingModule" in msg
        assert "TokenService" in msg
        assert "Auth" in msg

    def test_lists_exported_types(self):
        msg = format_visibility_error(
            "A", "AProv", "B", "Secret", ["PublicB", "OtherB"],
        )
        assert "PublicB" in msg
        assert "OtherB" in msg

    def test_contains_fix_suggestion(self):
        msg = format_visibility_error("A", "AP", "B", "S", [])
        assert "To fix:" in msg


class TestDuplicateModuleErrorFormat:
    def test_names_module(self):
        msg = format_duplicate_module_error("DbModule", "first call", "second call")
        assert "DbModule" in msg
        assert "first call" in msg
        assert "second call" in msg

    def test_contains_fix_suggestion(self):
        msg = format_duplicate_module_error("X", "a", "b")
        assert "To fix:" in msg
        assert "configured once" in msg


class TestNotAModuleErrorFormat:
    def test_names_entry(self):
        msg = format_not_a_module_error("MyClass", "str")
        assert "MyClass" in msg
        assert "not a valid module" in msg

    def test_contains_example(self):
        msg = format_not_a_module_error("Foo", "int")
        assert "@module" in msg
        assert "DynamicModule" in msg
```

---

### File 11: `tests/di/module/test_lifecycle.py`

```python
# file: tests/di/module/test_lifecycle.py
"""Tests for module lifecycle hooks — OnModuleInit, OnApplicationShutdown."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.di import ContainerRegistrarImpl, ContainerResolverImpl
from quadkit.contracts.core.lifecycle import OnModuleInit, OnApplicationBootstrap
from quadkit.di.container import Container
from quadkit.di.module import DynamicModule, module
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider, ProviderPriority


class _TrackingProvider(Provider):
    """Provider that records lifecycle events."""

    name = "tracking"
    calls: list[str] = []

    def __init__(self):
        super().__init__()
        self.__class__.calls = []

    async def register(self, container: ContainerRegistrarImpl) -> None:
        self.__class__.calls.append(f"{self.name}:register")

    async def boot(self, container: ContainerResolverImpl) -> None:
        self.__class__.calls.append(f"{self.name}:boot")

    async def shutdown(self) -> None:
        self.__class__.calls.append(f"{self.name}:shutdown")


class _InitTrackingProvider(_TrackingProvider, OnModuleInit):
    name = "init_tracking"

    async def on_module_init(self) -> None:
        self.__class__.calls.append(f"{self.name}:on_module_init")


class _BootstrapTrackingProvider(_TrackingProvider, OnApplicationBootstrap):
    name = "bootstrap_tracking"

    async def on_application_bootstrap(self) -> None:
        self.__class__.calls.append(f"{self.name}:on_application_bootstrap")


class TestOnModuleInit:
    """Test that OnModuleInit fires after boot."""

    @pytest.mark.asyncio
    async def test_on_module_init_called_after_boot(self):
        @module(providers=[_InitTrackingProvider])
        class MyModule:
            pass

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add_module(MyModule)

        await orchestrator.boot_all(container)

        assert "init_tracking:register" in _InitTrackingProvider.calls
        assert "init_tracking:boot" in _InitTrackingProvider.calls
        assert "init_tracking:on_module_init" in _InitTrackingProvider.calls

        # Order: register → boot → on_module_init
        reg_idx = _InitTrackingProvider.calls.index("init_tracking:register")
        boot_idx = _InitTrackingProvider.calls.index("init_tracking:boot")
        init_idx = _InitTrackingProvider.calls.index("init_tracking:on_module_init")
        assert reg_idx < boot_idx < init_idx

        await orchestrator.shutdown()


class TestOnApplicationBootstrap:
    """Test that OnApplicationBootstrap fires after ALL providers boot."""

    @pytest.mark.asyncio
    async def test_bootstrap_called_after_all_boot(self):
        @module(providers=[_BootstrapTrackingProvider])
        class MyModule:
            pass

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add_module(MyModule)

        await orchestrator.boot_all(container)

        assert "bootstrap_tracking:boot" in _BootstrapTrackingProvider.calls
        assert (
            "bootstrap_tracking:on_application_bootstrap"
            in _BootstrapTrackingProvider.calls
        )

        boot_idx = _BootstrapTrackingProvider.calls.index("bootstrap_tracking:boot")
        bootstrap_idx = _BootstrapTrackingProvider.calls.index(
            "bootstrap_tracking:on_application_bootstrap",
        )
        assert boot_idx < bootstrap_idx

        await orchestrator.shutdown()
```

---

### File 12: `tests/di/module/test_integration.py`

```python
# file: tests/di/module/test_integration.py
"""End-to-end integration tests — full Application boot with modules."""

from __future__ import annotations

import pytest

from quadkit.app.base import AppState, Application
from quadkit.config.main import QuadkitConfig
from quadkit.contracts.core.di import ContainerRegistrarImpl, ContainerResolverImpl
from quadkit.di.module import DynamicModule, Module, global_module, module
from quadkit.di.provider import Provider, ProviderPriority


# ---------------------------------------------------------------------------
# Test protocols (fake contracts)
# ---------------------------------------------------------------------------


class DatabaseSession:
    """Fake database session protocol."""


class CacheBackend:
    """Fake cache backend protocol."""


class AuthServiceProtocol:
    """Fake auth service protocol."""


class OrderServiceProtocol:
    """Fake order service protocol."""


# ---------------------------------------------------------------------------
# Test providers
# ---------------------------------------------------------------------------


class DbProvider(Provider):
    name = "db"
    priority = ProviderPriority.INFRASTRUCTURE
    provides = [DatabaseSession]

    def __init__(self, url: str = "sqlite:///test.db"):
        super().__init__()
        self.url = url

    async def register(self, container: ContainerRegistrarImpl) -> None:
        container.singleton(DatabaseSession, DatabaseSession)


class CacheProvider(Provider):
    name = "cache"
    priority = ProviderPriority.INFRASTRUCTURE
    provides = [CacheBackend]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        container.singleton(CacheBackend, CacheBackend)


class AuthProvider(Provider):
    name = "auth"
    priority = ProviderPriority.SECURITY
    provides = [AuthServiceProtocol]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        container.singleton(AuthServiceProtocol, AuthServiceProtocol)


class OrderProvider(Provider):
    name = "orders"
    priority = ProviderPriority.DOMAIN
    provides = [OrderServiceProtocol]

    async def register(self, container: ContainerRegistrarImpl) -> None:
        container.singleton(OrderServiceProtocol, OrderServiceProtocol)


# ---------------------------------------------------------------------------
# Test modules
# ---------------------------------------------------------------------------


@module()
class InfraModule(Module):
    @classmethod
    def configure(cls, db_url: str = "sqlite:///test.db") -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[DbProvider(url=db_url), CacheProvider()],
            exports=[DatabaseSession, CacheBackend],
            is_global=True,
        )


@module(
    providers=[AuthProvider],
    exports=[AuthServiceProtocol],
)
class AuthModule:
    pass


@module(
    imports=[AuthModule],
    providers=[OrderProvider],
    exports=[OrderServiceProtocol],
)
class OrderModule:
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullApplicationBoot:
    """Test complete application lifecycle with modules."""

    @pytest.mark.asyncio
    async def test_boot_with_modules(self):
        async with Application.boot(
            name="test-app",
            modules=[
                InfraModule.configure(db_url="sqlite:///test.db"),
                AuthModule,
                OrderModule,
            ],
        ) as app:
            assert app.state == AppState.RUNNING

            # All services should be resolvable
            db = await app.container.resolve(DatabaseSession)
            assert isinstance(db, DatabaseSession)

            cache = await app.container.resolve(CacheBackend)
            assert isinstance(cache, CacheBackend)

            auth = await app.container.resolve(AuthServiceProtocol)
            assert isinstance(auth, AuthServiceProtocol)

            orders = await app.container.resolve(OrderServiceProtocol)
            assert isinstance(orders, OrderServiceProtocol)

        assert app.state == AppState.STOPPED

    @pytest.mark.asyncio
    async def test_boot_with_modules_and_standalone(self):
        """Test mixing modules and standalone providers."""

        class StandaloneMetrics(Provider):
            name = "metrics"
            priority = ProviderPriority.LOW

            async def register(self, container: ContainerRegistrarImpl) -> None:
                pass

        async with Application.boot(
            name="test-app",
            modules=[InfraModule.configure()],
            providers=[StandaloneMetrics()],
        ) as app:
            assert app.state == AppState.RUNNING
            assert len(app.providers) >= 3  # 2 from InfraModule + 1 standalone

    @pytest.mark.asyncio
    async def test_module_provider_order(self):
        """Imported module providers should register before importers."""
        registration_order: list[str] = []

        class TrackingAuth(Provider):
            name = "auth"
            provides = [AuthServiceProtocol]

            async def register(self, container: ContainerRegistrarImpl) -> None:
                registration_order.append("auth")
                container.singleton(AuthServiceProtocol, AuthServiceProtocol)

        class TrackingOrder(Provider):
            name = "orders"
            provides = [OrderServiceProtocol]

            async def register(self, container: ContainerRegistrarImpl) -> None:
                registration_order.append("orders")
                container.singleton(OrderServiceProtocol, OrderServiceProtocol)

        @module(providers=[TrackingAuth], exports=[AuthServiceProtocol])
        class TrackAuthModule:
            pass

        @module(
            imports=[TrackAuthModule],
            providers=[TrackingOrder],
            exports=[OrderServiceProtocol],
        )
        class TrackOrderModule:
            pass

        async with Application.boot(
            name="test-app",
            modules=[TrackOrderModule],
        ) as app:
            assert registration_order.index("auth") < registration_order.index("orders")

    @pytest.mark.asyncio
    async def test_add_module_after_start_raises(self):
        app = Application(name="test-app")

        @module()
        class MyModule:
            pass

        app.add_module(MyModule)
        await app.start()

        with pytest.raises(RuntimeError, match="Cannot add_module after boot"):
            app.add_module(MyModule)

        await app.stop()

    @pytest.mark.asyncio
    async def test_health_check_with_modules(self):
        async with Application.boot(
            name="test-app",
            modules=[InfraModule.configure()],
        ) as app:
            health = await app.health_check()
            assert isinstance(health, dict)


class TestModuleBootWithClassmethod:
    """Test Application.boot() classmethod with modules parameter."""

    @pytest.mark.asyncio
    async def test_boot_classmethod_with_modules(self):
        async with Application.boot(
            name="boot-test",
            modules=[
                InfraModule.configure(),
                AuthModule,
            ],
        ) as app:
            assert app.state == AppState.RUNNING
            db = await app.container.resolve(DatabaseSession)
            assert db is not None

    @pytest.mark.asyncio
    async def test_boot_classmethod_providers_only(self):
        """Gear 2 style — providers only, no modules."""
        async with Application.boot(
            name="gear2-test",
            providers=[DbProvider(), CacheProvider()],
        ) as app:
            assert app.state == AppState.RUNNING
            db = await app.container.resolve(DatabaseSession)
            assert db is not None
```

---

### File 13: `tests/di/module/__init__.py`

```python
# file: tests/di/module/__init__.py
```

---

**Step 4 + Step 5 complete.** Full summary of everything delivered across all steps:

| Step | Files | Purpose |
|------|-------|---------|
| **Step 1** | `contracts/exceptions/provider.py`, `di/module/{__init__,constants,metadata,base,dynamic,decorator,introspection,graph,errors}.py` | Foundation types — exceptions, metadata, decorator, graph types, error formatting |
| **Step 2** | `di/module/compiler.py`, `di/module/registry.py` | The engine — 7-phase compiler + runtime ownership tracking |
| **Step 3** | `di/provider.py`, `di/resolution/descriptor.py`, `di/orchestrator.py` | Integration — `provides` ClassVar, `module_owner` field, compiler wired into orchestrator |
| **Step 4** | `contracts/core/module.py` | Cross-package protocols — external packages can type-hint against modules |
| **Step 5** | `tests/di/module/{conftest,test_decorator,test_dynamic,test_compiler,test_global,test_reexport,test_visibility,test_registry,test_errors,test_lifecycle,test_integration,__init__}.py` | 12 test files covering every aspect |

**The module system is now complete.** All files from the plan are delivered:

- ✅ `@module()` decorator with ClassVar inheritance
- ✅ `DynamicModule` + `configure()` / `for_feature()` pattern
- ✅ `ModuleCompiler` with cycle detection, import validation, re-export expansion, visibility computation
- ✅ `ModuleRegistry` with post-registration export validation
- ✅ `Application.add_module()` as primary Gear 3 API
- ✅ `Application.boot(modules=[...])` classmethod
- ✅ Global modules with universal visibility
- ✅ Re-exports
- ✅ Diagnostic error messages with fix suggestions
- ✅ Provider `provides` declaration for static export hints
- ✅ `ServiceDescriptor.module_owner` for diagnostics
- ✅ Contract-level protocols for cross-package usage
- ✅ Full test suite (12 files)