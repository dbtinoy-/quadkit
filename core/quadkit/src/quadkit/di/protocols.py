"""Internal protocols for the Quadkit DI subsystem.

These protocols are implementation details of the dependency injection
container. External consumers should depend on the public contracts in
``quadkit.contracts`` instead.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class DIResolverProtocol(Protocol):
    """Protocol for service resolution within the DI container.

    Used internally by the dependency injector to resolve services.
    External code should depend on ``ContainerResolverProtocol`` from contracts.
    """

    async def resolve(self, service_type: type[T]) -> T:
        """Asynchronously resolve a service by its registered type."""
        ...

    def has(self, service_type: object) -> bool:
        """Check if a service is registered."""
        ...

    def can_resolve(self, service_type: object) -> bool:
        """Check if a service can be resolved (includes auto-injectable)."""
        ...


@runtime_checkable
class TypeHintResolverProtocol(Protocol):
    """Protocol for resolving type hints and injectable parameters."""

    def get_injectable_parameters(self, cls: type) -> dict[str, Any]:
        """Get parameters that can be injected for a class."""
        ...

    def get_type_dependencies(self, cls: type) -> set[object]:
        """Get all dependency types for a class."""
        ...


@runtime_checkable
class DIServiceRegistryProtocol(Protocol):
    """Protocol for service registration management."""

    def has(self, service_type: object) -> bool:
        """Check if a service is registered."""
        ...

    def is_singleton(self, service_type: object) -> bool:
        """Check if a service is a singleton."""
        ...

    def is_singleton_instantiated(self, service_key: object) -> bool:
        """Check if a singleton has been instantiated."""
        ...

    def mark_singleton_instantiated(self, service_key: object) -> None:
        """Mark a singleton as instantiated."""
        ...

    def get_implementation(self, service_key: object) -> Any:
        """Get implementation for a service type."""
        ...

    @property
    def singletons(self) -> dict[object, Any]:
        """Get singleton instances/factories."""
        ...

    @property
    def services(self) -> dict[object, Any]:
        """Get transient service factories."""
        ...


@runtime_checkable
class ProtocolValidatorProtocol(Protocol):
    """Protocol for protocol validation."""

    def validate_registration(self, service_type: type, implementation: Any) -> None:
        """Validate registration conformance."""
        ...

    def validate_resolution(self, resolved_service: Any, expected_type: type) -> None:
        """Validate resolution conformance."""
        ...


@runtime_checkable
class InjectorProtocol(Protocol):
    """Protocol for dependency injection and instantiation."""

    async def instantiate(self, cls: type, force_inject: bool = False) -> Any:
        """Async instantiate a class with injection."""
        ...


__all__ = [
    "DIResolverProtocol",
    "DIServiceRegistryProtocol",
    "InjectorProtocol",
    "ProtocolValidatorProtocol",
    "TypeHintResolverProtocol",
]
