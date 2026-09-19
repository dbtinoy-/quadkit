# file: tests/di/module/test_dynamic.py
"""Tests for DynamicModule creation and usage."""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions.provider import ModuleError
from quadkit.di.module import DynamicModule, Module, module
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.di.provider import Provider, ProviderPriority


class ProtoA:
    """Fake protocol for testing exports."""


class ProtoB:
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
        assert "<DynamicModule 'MyModule'" in r
        assert "providers=[StubProviderA]" in r
        assert "exports=[ProtoA]" in r
        assert "is_global=True" in r

    def test_repr_lists_imports_and_instance_provider_types(self):
        @module()
        class ImportedModule:
            pass

        @module()
        class MyModule:
            pass

        dm = DynamicModule(
            module=MyModule,
            providers=[StubProviderA(), StubProviderB],
            imports=[ImportedModule],
            exports=[ProtoA, ProtoB],
        )

        r = repr(dm)

        assert "providers=[StubProviderA, StubProviderB]" in r
        assert "imports=[ImportedModule]" in r
        assert "exports=[ProtoA, ProtoB]" in r


class TestForRootPattern:
    """Test the configure() / scope() factory pattern."""

    def test_configure_returns_dynamic_module(self):
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

    def test_scope_returns_dynamic_module(self):
        @module()
        class DatabaseModule(Module):
            @classmethod
            def scope(cls, *models: type) -> DynamicModule:
                return DynamicModule(
                    module=cls,
                    providers=[StubProviderB],
                )

        dm = DatabaseModule.scope(str, int)
        assert isinstance(dm, DynamicModule)
        assert dm.module is DatabaseModule
        assert dm.is_global is False

    def test_configure_with_instance_providers(self):
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

    def test_module_class_repr_uses_metadata(self):
        @module(
            name="AuthModule",
            providers=[StubProviderA],
            exports=[ProtoA],
        )
        class AuthModule(Module):
            pass

        rendered = repr(AuthModule)

        assert "<Module 'AuthModule'" in rendered
        assert "providers=[StubProviderA]" in rendered
        assert "exports=[ProtoA]" in rendered


class TestDynamicModuleHealthProviders:
    """Test health_providers field."""

    def test_default_health_providers_is_none(self) -> None:
        @module()
        class MyModule:
            pass

        dm = DynamicModule(module=MyModule)
        assert dm.health_providers is None

    def test_health_providers_accepts_list_of_types(self) -> None:
        @module()
        class MyModule:
            pass

        class FakeService:
            pass

        dm = DynamicModule(module=MyModule, health_providers=[FakeService])
        assert dm.health_providers == [FakeService]

    def test_health_providers_accepts_list_of_strings(self) -> None:
        @module()
        class MyModule:
            pass

        dm = DynamicModule(module=MyModule, health_providers=["some.service.path"])
        assert dm.health_providers == ["some.service.path"]

    def test_health_providers_accepts_mixed_list(self) -> None:
        @module()
        class MyModule:
            pass

        class FakeService:
            pass

        dm = DynamicModule(
            module=MyModule, health_providers=[FakeService, "named.service"]
        )
        assert len(dm.health_providers) == 2
        assert FakeService in dm.health_providers
        assert "named.service" in dm.health_providers
