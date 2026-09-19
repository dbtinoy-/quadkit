"""Tests for the hardened module system (Phase 8).

Covers:
- Circular dependency detection
- Import validation (must be @module-decorated)
- ModuleError exception
- configure_builder with cycle detection
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.di.module import ModuleError, create_module

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class DummyProvider:
    """Minimal provider stand-in for testing."""

    name: str = "dummy"


class MockBuilder:
    """Builder stub that tracks provider registrations."""

    def __init__(self) -> None:
        self.added_providers: list[object] = []
        self._modules: set[type] = set()

    def add_provider(self, provider: object) -> None:
        self.added_providers.append(provider)

    def add_module(self, module_cls: type) -> None:
        self._modules.add(module_cls)


# ---------------------------------------------------------------------------
# Tests: Import validation
# ---------------------------------------------------------------------------


class TestImportValidation:
    """Verify that module imports are validated at construction."""

    def test_non_type_import_raises(self) -> None:
        """Importing a string instead of a class raises TypeError."""
        with pytest.raises(TypeError, match="not a class"):

            @create_module(name="bad", imports=["not_a_class"])
            class BadMod:
                pass

    def test_undecorated_class_import_raises(self) -> None:
        """Importing a plain class (no @module) raises TypeError."""

        class PlainClass:
            pass

        with pytest.raises(TypeError, match="not decorated with @module"):

            @create_module(name="bad", imports=[PlainClass])
            class BadMod:
                pass

    def test_valid_module_import_succeeds(self) -> None:
        """Importing a @module-decorated class succeeds."""

        @create_module(name="dep")
        class DepMod:
            pass

        @create_module(name="main", imports=[DepMod])
        class MainMod:
            pass

        assert hasattr(MainMod, "__quadkit_module__")


# ---------------------------------------------------------------------------
# Tests: Circular dependency detection
# ---------------------------------------------------------------------------


class TestCircularDependencyDetection:
    """Verify circular imports are detected during configure_builder."""

    def test_self_referencing_module_raises(self) -> None:
        """A module that imports itself is detected as circular."""

        @create_module(name="self_ref")
        class SelfRef:
            pass

        # Manually make it import itself (bypass __post_init__ validation
        # which doesn't check this since __quadkit_module__ isn't set yet)
        SelfRef.__quadkit_module__.imports = [SelfRef]

        builder = MockBuilder()
        with pytest.raises(ModuleError, match="Circular module dependency"):
            SelfRef.__quadkit_module__.configure_builder(builder)

    def test_two_module_cycle_raises(self) -> None:
        """A→B→A cycle is detected."""

        @create_module(name="a")
        class A:
            pass

        @create_module(name="b")
        class B:
            pass

        # Create circular: A imports B, B imports A
        A.__quadkit_module__.imports = [B]
        B.__quadkit_module__.imports = [A]

        builder = MockBuilder()
        with pytest.raises(ModuleError, match="Circular module dependency"):
            A.__quadkit_module__.configure_builder(builder)

    def test_no_cycle_works(self) -> None:
        """A→B without cycle configures correctly."""

        @create_module(name="leaf", providers=[DummyProvider])
        class LeafMod:
            pass

        @create_module(name="root", imports=[LeafMod])
        class RootMod:
            pass

        builder = MockBuilder()
        RootMod.__quadkit_module__.configure_builder(builder)

        assert LeafMod in builder._modules
        assert any(isinstance(p, DummyProvider) for p in builder.added_providers)


# ---------------------------------------------------------------------------
# Tests: ModuleError
# ---------------------------------------------------------------------------


class TestModuleError:
    """Verify ModuleError is properly exposed."""

    def test_module_error_is_exception(self) -> None:
        """ModuleError inherits from Exception."""
        assert issubclass(ModuleError, Exception)

    def test_module_error_in_all(self) -> None:
        """ModuleError is in __all__."""
        import importlib
        mod_module = importlib.import_module("quadkit.di.module")
        assert "ModuleError" in mod_module.__all__


# ---------------------------------------------------------------------------
# Tests: Module decorator
# ---------------------------------------------------------------------------


class TestModuleDecorator:
    """Verify the @module / create_module decorator."""

    def test_decorator_attaches_metadata(self) -> None:
        """@module sets __quadkit_module__ on the class."""

        @create_module(name="test_mod")
        class TestMod:
            pass

        assert hasattr(TestMod, "__quadkit_module__")
        assert TestMod.__quadkit_module__.name == "test_mod"

    def test_default_name_is_class_name(self) -> None:
        """Omitting name uses the class name."""

        @create_module()
        class MyModule:
            pass

        assert MyModule.__quadkit_module__.name == "MyModule"

    def test_owner_cls_set(self) -> None:
        """__quadkit_owner__ is set for cycle detection."""

        @create_module(name="owned")
        class OwnedMod:
            pass

        assert OwnedMod.__quadkit_module__.__quadkit_owner__ is OwnedMod
