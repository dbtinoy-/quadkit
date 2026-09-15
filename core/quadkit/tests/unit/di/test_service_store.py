"""Tests for ServiceStore in DI resolution."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.resolution.descriptor import ServiceDescriptor
from quadkit.di.resolution.store import ServiceStore


class FakeProtocol:
    """Fake protocol for testing."""


class FakeImplementation(FakeProtocol):
    """Fake implementation class for testing."""


def factory_function() -> FakeProtocol:
    """Factory function for testing."""
    return FakeImplementation()


class TestServiceStore:
    """Tests for ServiceStore."""

    def test_add_stores_descriptor(self) -> None:
        """Test adding a descriptor to the store."""
        store = ServiceStore()
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        store.add(descriptor)
        assert store.get(FakeProtocol) is descriptor

    def test_add_overwrites_existing(self) -> None:
        """Test adding overwrites existing registration."""
        store = ServiceStore()
        d1 = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        d2 = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        store.add(d1)
        store.add(d2)
        assert store.get(FakeProtocol) is d2

    def test_get_returns_none_for_missing(self) -> None:
        """Test get returns None for unregistered type."""
        store = ServiceStore()
        assert store.get(FakeProtocol) is None

    def test_has_returns_true_when_registered(self) -> None:
        """Test has returns True for registered type."""
        store = ServiceStore()
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        store.add(descriptor)
        assert store.has(FakeProtocol) is True

    def test_has_returns_false_when_not_registered(self) -> None:
        """Test has returns False for unregistered type."""
        store = ServiceStore()
        assert store.has(FakeProtocol) is False

    def test_all_returns_all_descriptors(self) -> None:
        """Test all returns all stored descriptors."""
        store = ServiceStore()
        d1 = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        d2 = ServiceDescriptor(
            service_type=str,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        store.add(d1)
        store.add(d2)
        all_descriptors = store.all()
        assert len(all_descriptors) == 2
        assert d1 in all_descriptors
        assert d2 in all_descriptors

    def test_all_returns_empty_list_when_empty(self) -> None:
        """Test all returns empty list for empty store."""
        store = ServiceStore()
        assert store.all() == []

    def test_all_returns_copy_not_reference(self) -> None:
        """Test all returns a copy, not the internal list."""
        store = ServiceStore()
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        store.add(descriptor)
        all_descriptors = store.all()
        all_descriptors.clear()
        assert len(store.all()) == 1

    def test_clear_removes_all_descriptors(self) -> None:
        """Test clear removes all descriptors."""
        store = ServiceStore()
        d1 = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        d2 = ServiceDescriptor(
            service_type=str,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        store.add(d1)
        store.add(d2)
        store.clear()
        assert store.all() == []
        assert store.has(FakeProtocol) is False

    def test_update_singleton_instance(self) -> None:
        """Test updating singleton instance."""
        store = ServiceStore()
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        store.add(descriptor)
        instance = FakeImplementation()
        store.update_singleton_instance(FakeProtocol, instance)
        updated = store.get(FakeProtocol)
        assert updated is not None
        assert updated.instance is instance
        assert updated.is_instantiated is True

    def test_update_singleton_instance_raises_for_missing(self) -> None:
        """Test update_singleton_instance raises for unregistered type."""
        store = ServiceStore()
        with pytest.raises(KeyError):
            store.update_singleton_instance(FakeProtocol, FakeImplementation())

    def test_update_singleton_instance_raises_for_non_singleton(self) -> None:
        """Test update_singleton_instance raises for non-singleton scope."""
        store = ServiceStore()
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        store.add(descriptor)
        with pytest.raises(ValueError, match="not a singleton"):
            store.update_singleton_instance(FakeProtocol, FakeImplementation())

    def test_is_singleton_true_for_singleton(self) -> None:
        """Test is_singleton returns True for singleton scope."""
        store = ServiceStore()
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        store.add(descriptor)
        assert store.is_singleton(FakeProtocol) is True

    def test_is_singleton_false_for_transient(self) -> None:
        """Test is_singleton returns False for transient scope."""
        store = ServiceStore()
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        store.add(descriptor)
        assert store.is_singleton(FakeProtocol) is False

    def test_is_singleton_false_for_unregistered(self) -> None:
        """Test is_singleton returns False for unregistered type."""
        store = ServiceStore()
        assert store.is_singleton(FakeProtocol) is False

    def test_transient_helper(self) -> None:
        """Test transient helper method."""
        store = ServiceStore()
        store.transient(FakeProtocol, factory_function)
        desc = store.get(FakeProtocol)
        assert desc is not None
        assert desc.scope == ServiceScope.TRANSIENT
        assert desc.implementation is factory_function

    def test_singleton_helper_with_factory(self) -> None:
        """Test singleton helper with factory."""
        store = ServiceStore()
        store.singleton(FakeProtocol, factory=factory_function)
        desc = store.get(FakeProtocol)
        assert desc is not None
        assert desc.scope == ServiceScope.SINGLETON

    def test_singleton_helper_with_instance(self) -> None:
        """Test singleton helper with pre-built instance."""
        store = ServiceStore()
        instance = FakeImplementation()
        store.singleton(FakeProtocol, instance=instance)
        desc = store.get(FakeProtocol)
        assert desc is not None
        assert desc.instance is instance
        assert desc.is_instantiated is True

    def test_singleton_helper_with_class_as_factory(self) -> None:
        """Test singleton helper with class as factory."""
        store = ServiceStore()
        store.singleton(FakeProtocol, factory=FakeImplementation)
        desc = store.get(FakeProtocol)
        assert desc is not None
        assert desc.scope == ServiceScope.SINGLETON
        assert desc.implementation is FakeImplementation

    def test_singleton_helper_with_name(self) -> None:
        """Test singleton helper with named registration."""
        store = ServiceStore()
        store.singleton(FakeProtocol, name="named_singleton", factory=factory_function)
        desc = store.get("named_singleton")
        assert desc is not None
        assert desc.scope == ServiceScope.SINGLETON

    def test_scoped_helper(self) -> None:
        """Test scoped helper method."""
        store = ServiceStore()
        store.scoped(FakeProtocol, factory_function)
        desc = store.get(FakeProtocol)
        assert desc is not None
        assert desc.scope == ServiceScope.SCOPED

    def test_scoped_helper_with_name(self) -> None:
        """Test scoped helper with named registration."""
        store = ServiceStore()
        store.scoped(FakeProtocol, factory_function, name="named_scoped")
        desc = store.get("named_scoped")
        assert desc is not None
        assert desc.scope == ServiceScope.SCOPED
