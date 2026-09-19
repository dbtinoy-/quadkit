"""Tests for DI ServiceDescriptor."""

import pytest

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.resolution.descriptor import ServiceDescriptor


class TestServiceDescriptor:
    """Tests for ServiceDescriptor dataclass."""

    def test_create_descriptor_with_all_fields(self) -> None:
        """Test creating a descriptor with all fields."""
        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.SINGLETON,
            instance="test",
            is_instantiated=True,
            module_owner="test_module",
        )

        assert descriptor.service_type is object
        assert descriptor.implementation is str
        assert descriptor.scope == ServiceScope.SINGLETON
        assert descriptor.instance == "test"
        assert descriptor.is_instantiated is True
        assert descriptor.module_owner == "test_module"

    def test_create_descriptor_with_defaults(self) -> None:
        """Test creating a descriptor with default values."""
        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.TRANSIENT,
        )

        assert descriptor.service_type is object
        assert descriptor.implementation is str
        assert descriptor.scope == ServiceScope.TRANSIENT
        assert descriptor.instance is None
        assert descriptor.is_instantiated is False
        assert descriptor.module_owner is None

    def test_is_factory_with_callable(self) -> None:
        """Test is_factory property with a callable factory."""

        def factory() -> str:
            return "test"

        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=factory,
            scope=ServiceScope.TRANSIENT,
        )

        assert descriptor.is_factory is True

    def test_is_factory_with_class(self) -> None:
        """Test is_factory property with a class."""
        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.TRANSIENT,
        )

        assert descriptor.is_factory is False

    def test_is_singleton(self) -> None:
        """Test is_singleton property."""
        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.SINGLETON,
        )

        assert descriptor.is_singleton is True
        assert descriptor.is_scoped is False
        assert descriptor.is_transient is False

    def test_is_scoped(self) -> None:
        """Test is_scoped property."""
        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.SCOPED,
        )

        assert descriptor.is_scoped is True
        assert descriptor.is_singleton is False
        assert descriptor.is_transient is False

    def test_is_transient(self) -> None:
        """Test is_transient property."""
        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.TRANSIENT,
        )

        assert descriptor.is_transient is True
        assert descriptor.is_singleton is False
        assert descriptor.is_scoped is False

    def test_with_instance(self) -> None:
        """Test with_instance method creates new descriptor with instance."""
        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.SINGLETON,
        )

        new_descriptor = descriptor.with_instance("test_instance")

        assert new_descriptor.service_type is object
        assert new_descriptor.implementation is str
        assert new_descriptor.scope == ServiceScope.SINGLETON
        assert new_descriptor.instance == "test_instance"
        assert new_descriptor.is_instantiated is True

    def test_with_instance_preserves_original(self) -> None:
        """Test that with_instance doesn't modify original descriptor."""
        original = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.SINGLETON,
        )

        original.with_instance("test_instance")

        assert original.instance is None
        assert original.is_instantiated is False

    def test_frozen_dataclass(self) -> None:
        """Test that descriptor is frozen (immutable)."""
        from dataclasses import FrozenInstanceError

        descriptor = ServiceDescriptor(
            service_type=object,
            implementation=str,
            scope=ServiceScope.SINGLETON,
        )

        with pytest.raises(FrozenInstanceError):
            descriptor.scope = ServiceScope.TRANSIENT
