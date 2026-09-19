"""Tests for di/module/introspection module."""

import pytest

from quadkit.di.module.introspection import (
    get_module_class,
    get_module_metadata,
    get_module_name,
    is_dynamic_module,
    is_module,
    resolve_module_input,
)
from quadkit.di.module.dynamic import DynamicModule
from quadkit.di.module.metadata import ModuleMetadata


class TestGetModuleMetadata:
    """Tests for get_module_metadata function."""

    def test_get_module_metadata_from_decorated(self) -> None:
        """Test getting metadata from decorated module."""
        from quadkit.di.module import module

        @module()
        class TestModule:
            pass

        meta = get_module_metadata(TestModule)
        assert meta is not None

    def test_get_module_metadata_not_decorated(self) -> None:
        """Test getting metadata from non-decorated class returns None."""

        class NotAModule:
            pass

        meta = get_module_metadata(NotAModule)
        assert meta is None


class TestIsModule:
    """Tests for is_module function."""

    def test_is_module_decorated(self) -> None:
        """Test is_module returns True for decorated class."""
        from quadkit.di.module import module

        @module()
        class TestModule:
            pass

        assert is_module(TestModule) is True

    def test_is_module_not_decorated(self) -> None:
        """Test is_module returns False for non-decorated class."""

        class NotAModule:
            pass

        assert is_module(NotAModule) is False


class TestIsDynamicModule:
    """Tests for is_dynamic_module function."""

    def test_is_dynamic_module_true(self) -> None:
        """Test is_dynamic_module returns True for DynamicModule."""
        from quadkit.di.module import module

        @module()
        class TestModule:
            pass

        dynamic = DynamicModule(module=TestModule)
        assert is_dynamic_module(dynamic) is True

    def test_is_dynamic_module_false(self) -> None:
        """Test is_dynamic_module returns False for regular class."""

        class RegularClass:
            pass

        assert is_dynamic_module(RegularClass) is False


class TestGetModuleName:
    """Tests for get_module_name function."""

    def test_get_module_name_from_metadata(self) -> None:
        """Test getting name from ModuleMetadata."""
        from quadkit.di.module import module

        @module()
        class TestModule:
            pass

        name = get_module_name(TestModule)
        assert name == "TestModule"

    def test_get_module_name_fallback(self) -> None:
        """Test fallback to class name when no metadata."""

        class MyModule:
            pass

        name = get_module_name(MyModule)
        assert name == "MyModule"

    def test_get_module_name_from_dynamic(self) -> None:
        """Test getting name from DynamicModule."""
        from quadkit.di.module import module

        @module()
        class ActualModule:
            pass

        dynamic = DynamicModule(module=ActualModule, name="my-dynamic")
        name = get_module_name(dynamic)
        assert name == "my-dynamic"


class TestGetModuleClass:
    """Tests for get_module_class function."""

    def test_get_module_class_from_class(self) -> None:
        """Test getting class from module class."""

        class TestModule:
            pass

        cls = get_module_class(TestModule)
        assert cls is TestModule

    def test_get_module_class_from_dynamic(self) -> None:
        """Test getting class from DynamicModule."""
        from quadkit.di.module import module

        @module()
        class ActualModule:
            pass

        dynamic = DynamicModule(module=ActualModule)
        cls = get_module_class(dynamic)
        assert cls is ActualModule


class TestResolveModuleInput:
    """Tests for resolve_module_input function."""

    def test_resolve_from_decorated_module(self) -> None:
        """Test resolving from decorated module class."""
        from quadkit.di.module import module

        @module()
        class TestModule:
            pass

        module_cls, meta, is_dynamic = resolve_module_input(TestModule)
        assert module_cls is TestModule
        assert is_dynamic is False

    def test_resolve_from_dynamic_module(self) -> None:
        """Test resolving from DynamicModule."""
        from quadkit.di.module import module

        @module()
        class ActualModule:
            pass

        dynamic = DynamicModule(module=ActualModule)
        module_cls, meta, is_dynamic = resolve_module_input(dynamic)
        assert module_cls is ActualModule
        assert meta is None
        assert is_dynamic is True

    def test_resolve_non_decorated_raises(self) -> None:
        """Test resolving non-decorated class raises ModuleError."""

        class NotAModule:
            pass

        with pytest.raises(Exception):
            resolve_module_input(NotAModule)

    def test_resolve_invalid_input_raises(self) -> None:
        """Test resolving invalid input raises ModuleError."""
        with pytest.raises(Exception):
            resolve_module_input("not a module")
