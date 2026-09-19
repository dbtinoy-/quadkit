"""Tests for ServiceDescriptor in DI resolution."""

import pytest
from unittest.mock import MagicMock

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.resolution.descriptor import ServiceDescriptor


class FakeProtocol:
    """Fake protocol for testing."""
    pass


class FakeImplementation(FakeProtocol):
    """Fake implementation class for testing."""
    pass


def factory_function() -> FakeProtocol:
    """Factory function for testing."""
    return FakeImplementation()


class TestServiceDescriptor:
    """Tests for ServiceDescriptor."""

    def test_basic_creation(self) -> None:
        """Test basic ServiceDescriptor creation."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        
        assert descriptor.service_type == FakeProtocol
        assert descriptor.implementation == FakeImplementation
        assert descriptor.scope == ServiceScope.TRANSIENT
        assert descriptor.instance is None
        assert descriptor.is_instantiated is False
        assert descriptor.module_owner is None

    def test_with_module_owner(self) -> None:
        """Test ServiceDescriptor with module_owner."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
            module_owner="test_module",
        )
        
        assert descriptor.module_owner == "test_module"

    def test_is_factory_with_class(self) -> None:
        """Test is_factory returns False for a class."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        
        assert descriptor.is_factory is False

    def test_is_factory_with_callable(self) -> None:
        """Test is_factory returns True for a callable factory."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=factory_function,
            scope=ServiceScope.TRANSIENT,
        )
        
        assert descriptor.is_factory is True

    def test_is_singleton(self) -> None:
        """Test is_singleton property."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        
        assert descriptor.is_singleton is True
        assert descriptor.is_scoped is False
        assert descriptor.is_transient is False

    def test_is_scoped(self) -> None:
        """Test is_scoped property."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SCOPED,
        )
        
        assert descriptor.is_scoped is True
        assert descriptor.is_singleton is False
        assert descriptor.is_transient is False

    def test_is_transient(self) -> None:
        """Test is_transient property."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        
        assert descriptor.is_transient is True
        assert descriptor.is_singleton is False
        assert descriptor.is_scoped is False

    def test_with_instance(self) -> None:
        """Test with_instance creates new descriptor with instance."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        
        instance = FakeImplementation()
        new_descriptor = descriptor.with_instance(instance)
        
        # Original should be unchanged
        assert descriptor.instance is None
        assert descriptor.is_instantiated is False
        
        # New descriptor should have instance
        assert new_descriptor.instance is instance
        assert new_descriptor.is_instantiated is True
        assert new_descriptor.service_type == descriptor.service_type
        assert new_descriptor.implementation == descriptor.implementation
        assert new_descriptor.scope == descriptor.scope

    def test_with_instance_preserves_module_owner(self) -> None:
        """Test with_instance preserves module_owner."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
            module_owner="test_module",
        )
        
        instance = FakeImplementation()
        new_descriptor = descriptor.with_instance(instance)
        
        assert new_descriptor.module_owner == "test_module"

    def test_repr_with_class(self) -> None:
        """Test __repr__ with class implementation."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        
        repr_str = repr(descriptor)
        
        assert "ServiceDescriptor" in repr_str
        assert "FakeProtocol" in repr_str
        assert "FakeImplementation" in repr_str
        assert "TRANSIENT" in repr_str
        assert "instantiated=False" in repr_str

    def test_repr_with_factory(self) -> None:
        """Test __repr__ with factory function implementation."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=factory_function,
            scope=ServiceScope.TRANSIENT,
        )
        
        repr_str = repr(descriptor)
        
        assert "ServiceDescriptor" in repr_str
        assert "FakeProtocol" in repr_str

    def test_repr_when_instantiated(self) -> None:
        """Test __repr__ when instantiated."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.SINGLETON,
        )
        
        instance = FakeImplementation()
        new_descriptor = descriptor.with_instance(instance)
        
        repr_str = repr(new_descriptor)
        
        assert "instantiated=True" in repr_str

    def test_frozen_dataclass(self) -> None:
        """Test that ServiceDescriptor is frozen (immutable)."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            descriptor.scope = ServiceScope.SINGLETON

    def test_slots(self) -> None:
        """Test that ServiceDescriptor uses slots."""
        descriptor = ServiceDescriptor(
            service_type=FakeProtocol,
            implementation=FakeImplementation,
            scope=ServiceScope.TRANSIENT,
        )
        
        # Should not have __dict__ due to slots
        assert not hasattr(descriptor, "__dict__")
