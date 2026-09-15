"""Tests for GraphValidator - DI dependency graph validation."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.resolution.descriptor import ServiceDescriptor
from quadkit.di.resolution.store import ServiceStore
from quadkit.di.resolution.validator import GraphValidator


class FakeProtocol:
    """Fake protocol for testing."""


class FakeImplementation(FakeProtocol):
    """Fake implementation class for testing."""

    def __init__(self, dep: object | None = None) -> None:
        self.dep = dep


class NoDependencies:
    """Class with no dependencies."""


class TestGraphValidator:
    """Tests for GraphValidator."""

    def test_empty_graph_is_valid(self) -> None:
        """Test empty store produces valid graph."""
        store = ServiceStore()
        validator = GraphValidator(store, None)
        errors = validator.validate_graph()
        assert errors == []

    def test_single_service_no_dependencies(self) -> None:
        """Test single service with no deps is valid."""
        store = ServiceStore()
        store.add(
            ServiceDescriptor(
                service_type=NoDependencies,
                implementation=NoDependencies,
                scope=ServiceScope.TRANSIENT,
            )
        )
        validator = GraphValidator(store, None)
        errors = validator.validate_graph()
        assert errors == []

    def test_circular_dependency_detected(self) -> None:
        """Test circular dependency is detected."""
        store = ServiceStore()
        store.add(
            ServiceDescriptor(
                service_type=FakeProtocol,
                implementation=FakeImplementation,
                scope=ServiceScope.TRANSIENT,
            )
        )
        store.add(
            ServiceDescriptor(
                service_type=FakeImplementation,
                implementation=FakeImplementation,
                scope=ServiceScope.TRANSIENT,
            )
        )
        validator = GraphValidator(store, None)
        validator._dependency_graph = {
            FakeProtocol: [FakeImplementation],
            FakeImplementation: [FakeProtocol],
        }
        errors = validator.validate_graph()
        assert any("Circular dependency" in e for e in errors)

    def test_missing_dependency_detected(self) -> None:
        """Test missing dependency is detected."""
        store = ServiceStore()
        store.add(
            ServiceDescriptor(
                service_type=FakeProtocol,
                implementation=FakeImplementation,
                scope=ServiceScope.TRANSIENT,
            )
        )
        # Don't add FakeImplementation to store, so it's seen as missing
        validator = GraphValidator(store, None)
        validator._dependency_graph = {
            FakeProtocol: [FakeImplementation],
        }
        errors = validator.validate_graph()
        assert len(errors) >= 1
        assert any("Missing dependency" in e for e in errors)

    def test_clear_removes_dependency_graph(self) -> None:
        """Test clear removes all tracked dependencies."""
        store = ServiceStore()
        validator = GraphValidator(store, None)
        validator._dependency_graph = {FakeProtocol: [FakeImplementation]}
        validator.clear()
        assert validator._dependency_graph == {}

    def test_update_for_descriptor_no_resolver(self) -> None:
        """Test update does nothing without type hint resolver."""
        store = ServiceStore()
        validator = GraphValidator(store, None)
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        validator.update_for_descriptor(descriptor)
        assert validator._dependency_graph == {}

    def test_update_for_descriptor_non_class(self) -> None:
        """Test update skips non-class implementations."""
        store = ServiceStore()
        validator = GraphValidator(store, None)

        def factory() -> None:
            pass

        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=factory,
            scope=ServiceScope.TRANSIENT,
        )
        validator.update_for_descriptor(descriptor)
        assert FakeProtocol not in validator._dependency_graph

    def test_validate_graph_empty_descriptors(self) -> None:
        """Test validate_graph handles empty descriptors dict."""
        store = ServiceStore()
        validator = GraphValidator(store, None)
        errors = validator.validate_graph()
        assert errors == []

    def test_validate_graph_skips_builtins(self) -> None:
        """Test missing dependency skips builtins like str, int."""
        store = ServiceStore()
        store.add(
            ServiceDescriptor(
                service_type=FakeProtocol,
                implementation=FakeImplementation,
                scope=ServiceScope.TRANSIENT,
            )
        )
        validator = GraphValidator(store, None)
        validator._dependency_graph = {
            FakeProtocol: [str],  # str is builtin
        }
        errors = validator.validate_graph()
        assert errors == []

    def test_validate_graph_multiple_services(self) -> None:
        """Test multiple services are all checked."""
        store = ServiceStore()
        store.add(
            ServiceDescriptor(
                service_type=NoDependencies,
                implementation=NoDependencies,
                scope=ServiceScope.TRANSIENT,
            )
        )
        store.add(
            ServiceDescriptor(
                service_type=FakeProtocol,
                implementation=FakeImplementation,
                scope=ServiceScope.TRANSIENT,
            )
        )
        validator = GraphValidator(store, None)
        validator._dependency_graph = {
            NoDependencies: [],
            FakeProtocol: [],
        }
        errors = validator.validate_graph()
        assert errors == []

    def test_validate_complex_cycle(self) -> None:
        """Test complex multi-node cycle detection."""
        store = ServiceStore()

        class A:
            pass

        class B:
            pass

        class C:
            pass

        store.add(
            ServiceDescriptor(
                service_type=A, implementation=A, scope=ServiceScope.TRANSIENT
            )
        )
        store.add(
            ServiceDescriptor(
                service_type=B, implementation=B, scope=ServiceScope.TRANSIENT
            )
        )
        store.add(
            ServiceDescriptor(
                service_type=C, implementation=C, scope=ServiceScope.TRANSIENT
            )
        )

        validator = GraphValidator(store, None)
        validator._dependency_graph = {
            A: [B],
            B: [C],
            C: [A],  # Creates A -> B -> C -> A cycle
        }
        errors = validator.validate_graph()
        assert len(errors) == 1
        assert "Circular dependency" in errors[0]

    def test_check_eager_cycle_raises_on_cycle(self) -> None:
        """Test _check_eager_cycle raises for cycles."""
        from quadkit.contracts.exceptions import CircularDependencyError

        store = ServiceStore()
        validator = GraphValidator(store, None)
        validator._dependency_graph = {
            FakeProtocol: [FakeImplementation],
            FakeImplementation: [FakeProtocol],
        }
        with pytest.raises(CircularDependencyError):
            validator._check_eager_cycle(FakeProtocol)

    def test_check_eager_cycle_no_cycle(self) -> None:
        """Test _check_eager_cycle does not raise for valid graph."""
        store = ServiceStore()
        validator = GraphValidator(store, None)
        validator._dependency_graph = {
            FakeProtocol: [],
            FakeImplementation: [],
        }
        validator._check_eager_cycle(FakeProtocol)  # Should not raise

    def test_check_eager_cycle_missing_key(self) -> None:
        """Test _check_eager_cycle handles missing key."""
        store = ServiceStore()
        validator = GraphValidator(store, None)
        validator._dependency_graph = {}
        validator._check_eager_cycle(FakeProtocol)  # Should not raise

    def test_build_dependency_graph_rebuilds(self) -> None:
        """Test _build_dependency_graph rebuilds from store."""
        store = ServiceStore()
        store.add(
            ServiceDescriptor(
                service_type=NoDependencies,
                implementation=NoDependencies,
                scope=ServiceScope.TRANSIENT,
            )
        )
        validator = GraphValidator(store, None)
        graph = validator._build_dependency_graph()
        assert isinstance(graph, dict)
