"""Service descriptor for DI container.

This module provides the ServiceDescriptor class that encapsulates
all information about a registered service in a single structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.core.scopes import ServiceScope


@dataclass(frozen=True, slots=True)
class ServiceDescriptor:
    """Descriptor for a registered service.

    This is the canonical representation of a service registration.
    All services are stored as descriptors in the registry.

    Attributes:
        service_type: The abstract type (interface/protocol). Named
            registrations store a ``(type, name)`` tuple as the key.
        implementation: The concrete type, factory callable, or a
            pre-built instance (stored by some named registrations)
        scope: How instances are managed (transient/singleton/scoped)
        instance: Cached instance for singletons (set after first resolution)
        module_owner: The name of the module that registered this service.
            ``None`` for services registered by standalone providers or
            direct container calls.  Used for diagnostics and
            module-aware visibility enforcement.
    """

    service_type: type | str | tuple[type, str]
    implementation: Any
    scope: ServiceScope
    instance: Any = field(default=None, compare=False)
    is_instantiated: bool = field(default=False, compare=False)
    module_owner: str | None = None

    @property
    def is_factory(self) -> bool:
        """Check if implementation is a callable factory (not a class)."""
        return callable(self.implementation) and not isinstance(
            self.implementation,
            type,
        )

    @property
    def is_singleton(self) -> bool:
        """Check if scope is singleton."""
        return self.scope == ServiceScope.SINGLETON

    @property
    def is_scoped(self) -> bool:
        """Check if scope is scoped."""
        return self.scope == ServiceScope.SCOPED

    @property
    def is_transient(self) -> bool:
        """Check if scope is transient."""
        return self.scope == ServiceScope.TRANSIENT

    def with_instance(self, instance: Any) -> ServiceDescriptor:
        """Create a new descriptor with the instance set (for singletons)."""
        return ServiceDescriptor(
            service_type=self.service_type,
            implementation=self.implementation,
            scope=self.scope,
            instance=instance,
            is_instantiated=True,
            module_owner=self.module_owner,
        )

    def __repr__(self) -> str:
        # include type names to avoid heavy objects in debug logs
        impl = (
            self.implementation.__name__
            if isinstance(self.implementation, type)
            else repr(self.implementation)
        )
        service_type_name = (
            self.service_type.__name__
            if isinstance(self.service_type, type)
            else str(self.service_type)
        )
        return (
            f"ServiceDescriptor(service_type={service_type_name}, "
            f"implementation={impl}, scope={self.scope.name}, "
            f"instantiated={self.is_instantiated})"
        )
