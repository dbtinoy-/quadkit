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
from .conftest import StubProviderA, StubProviderB, ProtoA, ProtoB


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
        assert meta.providers == []
        assert meta.imports == []
        assert meta.exports == []
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
        assert meta.providers == [StubProviderA]
        assert meta.exports == [ProtoA]
        assert meta.is_global is True

    def test_empty_factory_decorator(self):
        @module()
        class MyModule:
            pass

        meta = get_module_metadata(MyModule)
        assert meta.name == "MyModule"
        assert meta.providers == []

    def test_metadata_owner_set(self):
        @module(providers=[StubProviderA])
        class MyModule:
            pass

        meta = get_module_metadata(MyModule)
        assert meta.__quadkit_owner__ is MyModule

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
        assert meta.providers == [StubProviderA]
        assert meta.exports == [ProtoA]


class TestCreateModule:
    """Test create_module convenience function."""

    def test_create_module_as_decorator(self):
        @create_module(name="Infra", providers=[StubProviderA])
        class InfraModule:
            pass

        meta = get_module_metadata(InfraModule)
        assert meta.name == "Infra"
        assert meta.providers == [StubProviderA]


class TestClassVarInheritance:
    """Test that @module reads ClassVar defaults from Module base."""

    def test_reads_classvars_from_base(self):
        @module()
        class MyModule(Module):
            providers = [StubProviderA, StubProviderB]
            exports = [ProtoA]

        meta = get_module_metadata(MyModule)
        assert meta.providers == [StubProviderA, StubProviderB]
        assert meta.exports == [ProtoA]

    def test_decorator_args_override_classvars(self):
        @module(exports=[ProtoB])
        class MyModule(Module):
            providers = [StubProviderA]
            exports = [ProtoA]  # This should be overridden

        meta = get_module_metadata(MyModule)
        assert meta.providers == [StubProviderA]  # from ClassVar
        assert meta.exports == [ProtoB]  # from decorator

    def test_intermediate_base_inheritance(self):
        class BaseInfra(Module):
            providers = [StubProviderA]

        @module()
        class FullInfra(BaseInfra):
            exports = [ProtoA]

        meta = get_module_metadata(FullInfra)
        assert meta.providers == [StubProviderA]  # inherited
        assert meta.exports == [ProtoA]  # own

    def test_module_base_defaults_not_inherited(self):
        """Module base class empty lists should not leak."""

        @module()
        class MyModule(Module):
            pass

        meta = get_module_metadata(MyModule)
        assert meta.providers == []
        assert meta.imports == []
        assert meta.exports == []

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

    def test_invalid_import_not_a_class_raises(self):
        with pytest.raises(TypeError, match="not a class"):
            @module(imports=[42])  # type: ignore[list-item]
            class BadModule:
                pass

    def test_invalid_import_not_decorated_raises(self):
        class PlainClass:
            pass

        with pytest.raises(TypeError, match="not decorated with @module"):
            @module(imports=[PlainClass])
            class BadModule:
                pass


class TestModuleInstanceAsDecorator:
    """Test using a Module() instance directly as a class decorator."""

    def test_module_instance_as_decorator(self):
        """Module(imports=[...]) instance used as class decorator."""
        from quadkit.di.module import ModuleBase

        @module(providers=[StubProviderA])
        class UserModule:
            pass

        @Module(imports=[UserModule])
        class AppModule(ModuleBase):
            pass

        assert is_module(AppModule)
        meta = get_module_metadata(AppModule)
        assert meta.imports == [UserModule]

    def test_module_base_alias(self):
        """ModuleBase is Module."""
        from quadkit.di.module import ModuleBase

        assert ModuleBase is Module
