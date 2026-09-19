"""Tests for di/resolution/descriptor module."""
import pytest
from unittest.mock import MagicMock

from quadkit.di.resolution.descriptor import ServiceDescriptor
from quadkit.contracts.core.scopes import ServiceScope


class TestServiceDescriptor:
    """Tests for ServiceDescriptor class."""

    def test_create_descriptor(self) -> None:
        """Test creating a basic ServiceDescriptor."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SINGLETON,
        )
        assert descriptor.service_type == MagicMock
        assert descriptor.implementation == MagicMock
        assert descriptor.scope == ServiceScope.SINGLETON
        assert descriptor.instance is None
        assert descriptor.is_instantiated is False
        assert descriptor.module_owner is None

    def test_create_with_module_owner(self) -> None:
        """Test creating descriptor with module_owner."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.TRANSIENT,
            module_owner="test.module",
        )
        assert descriptor.module_owner == "test.module"

    def test_is_factory_class(self) -> None:
        """Test is_factory returns False for class implementation."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.TRANSIENT,
        )
        assert descriptor.is_factory is False

    def test_is_factory_callable(self) -> None:
        """Test is_factory returns True for callable factory."""
        def factory():
            pass

        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=factory,
            scope=ServiceScope.TRANSIENT,
        )
        assert descriptor.is_factory is True

    def test_is_singleton_true(self) -> None:
        """Test is_singleton returns True for singleton scope."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SINGLETON,
        )
        assert descriptor.is_singleton is True

    def test_is_singleton_false(self) -> None:
        """Test is_singleton returns False for non-singleton scope."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.TRANSIENT,
        )
        assert descriptor.is_singleton is False

    def test_is_scoped_true(self) -> None:
        """Test is_scoped returns True for scoped scope."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SCOPED,
        )
        assert descriptor.is_scoped is True

    def test_is_scoped_false(self) -> None:
        """Test is_scoped returns False for non-scoped scope."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SINGLETON,
        )
        assert descriptor.is_scoped is False

    def test_is_transient_true(self) -> None:
        """Test is_transient returns True for transient scope."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.TRANSIENT,
        )
        assert descriptor.is_transient is True

    def test_is_transient_false(self) -> None:
        """Test is_transient returns False for non-transient scope."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SINGLETON,
        )
        assert descriptor.is_transient is False

    def test_with_instance(self) -> None:
        """Test with_instance creates new descriptor with instance."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SINGLETON,
        )
        instance = MagicMock()
        new_descriptor = descriptor.with_instance(instance)

        assert new_descriptor.instance is instance
        assert new_descriptor.is_instantiated is True
        assert new_descriptor.service_type == descriptor.service_type
        assert new_descriptor.implementation == descriptor.implementation
        assert new_descriptor.scope == descriptor.scope
        assert new_descriptor.module_owner == descriptor.module_owner

    def test_repr_class_implementation(self) -> None:
        """Test repr with class implementation."""
        class TestService:
            pass

        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=TestService,
            scope=ServiceScope.SINGLETON,
        )
        r = repr(descriptor)
        assert "TestService" in r
        assert "service_type=" in r
        assert "scope=SINGLETON" in r

    def test_repr_callable_implementation(self) -> None:
        """Test repr with callable factory."""
        def factory():
            pass

        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=factory,
            scope=ServiceScope.TRANSIENT,
        )
        r = repr(descriptor)
        assert "implementation=" in r

    def test_immutable(self) -> None:
        """Test that descriptor is frozen (immutable)."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SINGLETON,
        )
        with pytest.raises(AttributeError):
            descriptor.instance = MagicMock()

    def test_slots(self) -> None:
        """Test that descriptor uses slots."""
        descriptor = ServiceDescriptor(
            service_type=MagicMock,
            implementation=MagicMock,
            scope=ServiceScope.SINGLETON,
        )
        # Frozen dataclass prevents attribute assignment
        with pytest.raises((AttributeError, TypeError)):
            descriptor.new_attr = "value"


class TestServiceDescriptorScopes:
    """Tests for different scope values."""

    def test_all_scopes(self) -> None:
        """Test creating descriptors with all scope types."""
        for scope in ServiceScope:
            descriptor = ServiceDescriptor(
                service_type=MagicMock,
                implementation=MagicMock,
                scope=scope,
            )
            assert descriptor.scope == scope