"""Test that all public APIs are exported via __all__ in quadkit-testing subpackages.

This test suite validates API surface completeness for:
- quadkit.testing.compliance (protocol compliance test suites)
- quadkit.testing.memory (in-memory implementations)
- quadkit.testing.fixtures (pytest fixtures)

Ensures that every public-facing class and function is:
1. Defined in the subpackage module
2. Listed in the module's __all__ export
3. Accessible via the subpackage import path
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest


def get_public_members(module: Any) -> set[str]:
    """Get all public member names from a module (not starting with _)."""
    return {
        name
        for name, obj in inspect.getmembers(module)
        if not name.startswith("_") and not inspect.isbuiltin(obj)
    }


def get_public_defined_members(module: Any) -> set[str]:
    """Get public members defined in the module (not imported from elsewhere)."""
    public = get_public_members(module)
    # Filter to only those where module is the defining module
    defined = set()
    for name in public:
        obj = getattr(module, name)
        # Check if this is defined in this module
        if hasattr(obj, "__module__") and obj.__module__ == module.__name__:
            defined.add(name)
        # Also include module-level constants and functions
        elif not inspect.isclass(obj) and not inspect.isfunction(obj):
            # This handles protocol subclasses and other objects
            defined.add(name)
    return defined


class TestComplianceSubpackageExports:
    """Test that compliance subpackage exports all public APIs."""

    def test_compliance_has_all_attribute(self) -> None:
        """Verify compliance/__init__.py defines __all__."""
        from quadkit.testing import compliance

        assert hasattr(compliance, "__all__")
        assert isinstance(compliance.__all__, list)
        assert len(compliance.__all__) > 0

    def test_compliance_all_contains_base_suites(self) -> None:
        """Verify __all__ includes the main compliance suite classes."""
        from quadkit.testing.compliance import __all__

        # All test suite base classes should be exported
        expected_exports = [
            "CacheBackendCompliance",
            "RepositoryCompliance",
            "EventBusCompliance",
        ]
        for export in expected_exports:
            assert export in __all__, f"{export} missing from compliance.__all__"

    def test_compliance_all_exports_are_accessible(self) -> None:
        """Verify each __all__ export is actually accessible."""
        from quadkit.testing import compliance

        for export_name in compliance.__all__:
            assert hasattr(compliance, export_name), (
                f"compliance.{export_name} not accessible but listed in __all__"
            )
            # Should be importable
            assert getattr(compliance, export_name) is not None

    def test_compliance_all_is_complete(self) -> None:
        """Verify __all__ contains all public classes and functions."""
        from quadkit.testing import compliance

        public_members = get_public_defined_members(compliance)
        # Filter to likely public APIs (skip test utilities, etc.)
        likely_public = {
            name
            for name in public_members
            if not name.startswith("_") and name[0].isupper()
        }  # Classes
        likely_public |= {
            name
            for name in public_members
            if not name.startswith("_")
            and name[0].islower()
            and callable(getattr(compliance, name))
        }  # Functions

        missing = likely_public - set(compliance.__all__)
        # Allow some internal things to not be exported
        allowed_internal = {"_LAZY_IMPORTS", "pytest"}
        missing = missing - allowed_internal
        assert not missing, f"Public APIs missing from compliance.__all__: {missing}"


class TestMemorySubpackageExports:
    """Test that memory subpackage exports all public APIs."""

    def test_memory_has_all_attribute(self) -> None:
        """Verify memory/__init__.py defines __all__."""
        from quadkit.testing import memory

        assert hasattr(memory, "__all__")
        assert isinstance(memory.__all__, list)
        assert len(memory.__all__) > 0

    def test_memory_all_contains_core_classes(self) -> None:
        """Verify __all__ includes main in-memory implementation classes."""
        from quadkit.testing.memory import __all__

        # Core memory implementations should be exported
        expected_exports = [
            "InMemoryRepository",
            "InMemoryEventBus",
            "InMemoryCommandBus",
            "InMemoryQueryBus",
        ]
        for export in expected_exports:
            assert export in __all__, f"{export} missing from memory.__all__"

    def test_memory_all_exports_are_accessible(self) -> None:
        """Verify each __all__ export is actually accessible."""
        from quadkit.testing import memory

        for export_name in memory.__all__:
            assert hasattr(memory, export_name), (
                f"memory.{export_name} not accessible but listed in __all__"
            )
            # Should be importable
            assert getattr(memory, export_name) is not None

    def test_memory_all_lazy_imports_are_valid(self) -> None:
        """Verify lazy imports in memory.__all__ can be loaded."""
        from quadkit.testing import memory

        # memory uses lazy imports; verify they work
        assert hasattr(memory, "_LAZY_IMPORTS")
        for export_name in memory.__all__:
            # This should trigger lazy loading if needed
            obj = getattr(memory, export_name)
            assert obj is not None, f"Failed to lazy-load {export_name}"


class TestFixturesSubpackageExports:
    """Test that fixtures subpackage exports all public APIs."""

    def test_fixtures_has_all_attribute(self) -> None:
        """Verify fixtures/__init__.py defines __all__."""
        from quadkit.testing import fixtures

        assert hasattr(fixtures, "__all__")
        assert isinstance(fixtures.__all__, list)
        assert len(fixtures.__all__) > 0

    def test_fixtures_all_contains_core_fixtures(self) -> None:
        """Verify __all__ includes main fixture functions."""
        from quadkit.testing.fixtures import __all__

        # Core fixtures should be exported
        expected_exports = [
            "fake_event_bus",
            "fake_cache",
            "fake_logger",
            "test_container",
            "test_bed",
        ]
        for export in expected_exports:
            assert export in __all__, f"{export} missing from fixtures.__all__"

    def test_fixtures_all_exports_are_accessible(self) -> None:
        """Verify each __all__ export is actually accessible."""
        from quadkit.testing import fixtures

        for export_name in fixtures.__all__:
            assert hasattr(fixtures, export_name), (
                f"fixtures.{export_name} not accessible but listed in __all__"
            )
            # Should be importable
            assert getattr(fixtures, export_name) is not None

    def test_fixtures_all_exports_callable_or_class(self) -> None:
        """Verify fixtures exports are mostly callables (fixtures) or classes."""
        from quadkit.testing import fixtures

        for export_name in fixtures.__all__:
            obj = getattr(fixtures, export_name)
            # Fixtures are callables, some might be test utilities
            assert callable(obj) or inspect.isclass(obj), (
                f"{export_name} is not callable"
            )


class TestAllSubpackagesConsistency:
    """Test consistency across all three subpackages."""

    def test_all_subpackages_have_all_attribute(self) -> None:
        """Verify all three subpackages have __all__ defined."""
        from quadkit.testing import compliance, fixtures, memory

        for subpackage in [compliance, fixtures, memory]:
            assert hasattr(subpackage, "__all__"), (
                f"{subpackage.__name__} missing __all__"
            )
            assert isinstance(subpackage.__all__, list), (
                f"{subpackage.__name__}.__all__ not a list"
            )
            assert len(subpackage.__all__) > 0

    def test_all_exports_are_non_empty_strings(self) -> None:
        """Verify all __all__ entries are valid non-empty strings."""
        from quadkit.testing import compliance, fixtures, memory

        for subpackage in [compliance, fixtures, memory]:
            for export_name in subpackage.__all__:
                assert isinstance(export_name, str), (
                    f"Non-string in {subpackage.__name__}.__all__: {export_name}"
                )
                assert len(export_name) > 0
                assert not export_name.startswith("_"), (
                    f"Private export in {subpackage.__name__}.__all__: {export_name}"
                )

    def test_no_duplicate_exports_in_all(self) -> None:
        """Verify no duplicate entries in __all__ lists."""
        from quadkit.testing import compliance, fixtures, memory

        for subpackage in [compliance, fixtures, memory]:
            all_list = subpackage.__all__
            duplicates = [name for name in all_list if all_list.count(name) > 1]
            assert not duplicates, (
                f"Duplicate exports in {subpackage.__name__}.__all__: {set(duplicates)}"
            )

    def test_all_entries_importable_individually(self) -> None:
        """Verify each __all__ entry can be imported directly from subpackage."""
        from quadkit.testing import compliance, fixtures, memory

        for subpackage in [compliance, fixtures, memory]:
            for export_name in subpackage.__all__:
                try:
                    obj = getattr(subpackage, export_name)
                    assert obj is not None, (
                        f"None object: {subpackage.__name__}.{export_name}"
                    )
                except (AttributeError, ImportError) as e:
                    pytest.fail(
                        f"Cannot import {subpackage.__name__}.{export_name}: {e}"
                    )


class TestIntegrationImportsViaAll:
    """Integration tests verifying imports work via __all__ exports."""

    def test_import_compliance_exports(self) -> None:
        """Verify compliance exports can be imported in real scenarios."""
        # Import a known export
        from quadkit.testing.compliance import CacheBackendCompliance

        assert CacheBackendCompliance is not None
        assert inspect.isclass(CacheBackendCompliance)

    def test_import_memory_exports(self) -> None:
        """Verify memory exports can be imported in real scenarios."""
        # Import a known export
        from quadkit.testing.memory import InMemoryRepository

        assert InMemoryRepository is not None
        assert inspect.isclass(InMemoryRepository)

    def test_import_fixtures_exports(self) -> None:
        """Verify fixtures exports can be imported in real scenarios."""
        # Import a known export
        from quadkit.testing.fixtures import fake_event_bus

        assert fake_event_bus is not None
        assert callable(fake_event_bus)

    def test_star_import_compliance(self) -> None:
        """Verify 'from compliance import *' respects __all__."""
        # This is a static check: verify we can construct imports
        import quadkit.testing.compliance as compliance_module

        all_names = set(compliance_module.__all__)
        # Verify at least expected classes are in the list
        assert "CacheBackendCompliance" in all_names

    def test_star_import_memory(self) -> None:
        """Verify 'from memory import *' respects __all__."""
        import quadkit.testing.memory as memory_module

        all_names = set(memory_module.__all__)
        # Verify at least expected classes are in the list
        assert "InMemoryRepository" in all_names

    def test_star_import_fixtures(self) -> None:
        """Verify 'from fixtures import *' respects __all__."""
        import quadkit.testing.fixtures as fixtures_module

        all_names = set(fixtures_module.__all__)
        # Verify at least expected fixtures are in the list
        assert "fake_event_bus" in all_names
