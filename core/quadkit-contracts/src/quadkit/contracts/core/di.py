"""Dependency injection protocols for Quadkit Framework."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Protocol,
    TypeVar,
    overload,
    runtime_checkable,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.exceptions.container import OrphanedRegistration


T = TypeVar("T")


@runtime_checkable
class ContainerRegistrarProtocol(Protocol):
    """Protocol for registering dependencies in the container.

    Used during the registration phase where resolution is not yet permitted.
    """

    def transient(
        self,
        service_type: type[T],
        factory: Any,
        validate: bool = True,
    ) -> None:
        """Register a transient service."""
        ...

    @overload
    def singleton(
        self,
        service_type: type[T],
        instance: T | None = None,
        *,
        name: str | None = None,
        factory: Any | None = None,
        validate: bool = True,
    ) -> None: ...

    @overload
    def singleton(
        self,
        service_type: Any,
        instance: Any = None,
        *,
        name: str | None = None,
        factory: Any | None = None,
        validate: bool = True,
    ) -> None: ...

    def singleton(
        self,
        service_type: Any,
        instance: Any = None,
        *,
        name: str | None = None,
        factory: Any | None = None,
        validate: bool = True,
    ) -> None:
        """Register a singleton service (shared instance).

        Args:
            service_type: The abstract type (protocol/class) being registered.
                Accepts both concrete classes (``type[T]`` with full type
                inference) and Protocol types (via ``Any`` fallback).
            instance: Pre-built singleton instance.
            name: Optional string key. When provided, the binding is stored
                under this name instead of ``service_type``. Resolve via
                ``Annotated[T, Named(name)]``.
            factory: Factory callable for lazy creation.
            validate: Whether to validate protocol conformance.
        """
        ...

    def scoped(
        self,
        service_type: type[T],
        factory: Any,
        validate: bool = True,
        *,
        name: str | None = None,
    ) -> None:
        """Register a scoped service (one instance per scope).

        Args:
            service_type: The abstract type being registered.
            factory: Factory callable, called once per scope.
            validate: Whether to validate protocol conformance.
            name: Optional string key for named scoped registration.
                Resolve via ``Annotated[T, Named(name)]``.
        """
        ...

    def has(self, service_type: Any) -> bool:
        """Check if a service is registered."""
        ...

    def bind(
        self,
        service_type: type[T],
        instance: T,
    ) -> None:
        """Bind a pre-built singleton instance, overwriting any existing binding.

        Unlike ``singleton()``, this works on frozen containers.  Designed for
        updating singleton instances during the boot phase (e.g. wrapping a
        store with a tenancy decorator).

        The service *must* already be registered as a singleton.

        Args:
            service_type: The registered service type to rebind.
            instance: The replacement singleton instance.
        """
        ...


@runtime_checkable
class ContainerResolverProtocol(Protocol):
    """Protocol for resolving dependencies from the container.

    Async-first code should depend on this protocol. It provides only an
    asynchronous ``resolve()`` method and makes no guarantees about sync
    behaviour. All synchronous helpers have been removed to keep the API
    simple and forward‑looking.

    Used during the boot phase and runtime after registration is complete.
    """

    @overload
    async def resolve(
        self,
        service_type: type[T],
        *,
        bypass_visibility: bool = False,
    ) -> T: ...

    @overload
    async def resolve(
        self,
        service_type: Any,
        *,
        bypass_visibility: bool = False,
    ) -> Any: ...

    async def resolve(
        self,
        service_type: Any,
        *,
        bypass_visibility: bool = False,
    ) -> Any:
        """Asynchronously resolve a service by its type.

        The framework is async-first and does not support string or other
        loose keys. Consumers should only register and resolve using types
        so that the DI container remains fully type-safe.

        Accepts both concrete classes (``type[T]`` with full return-type
        inference) and Protocol types (via ``Any`` fallback).

        Args:
            service_type: The service type to resolve.
            bypass_visibility: If True, skip module visibility enforcement.
                Use only in framework-internal resolution paths.
        """
        ...

    async def call(
        self,
        func: Callable[..., Awaitable[T] | T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Call a function with dependency injection."""
        ...

    def create_scope(self) -> Any:
        """Create a request-scoped resolution context."""
        ...

    def has(self, service_type: Any) -> bool:
        """Check if a service is registered."""
        ...

    def bind(
        self,
        service_type: type[T],
        instance: T,
    ) -> None:
        """Bind a pre-built singleton instance, overwriting any existing binding.

        Works on frozen containers and is designed for updating singleton
        instances during the boot phase (e.g. wrapping a store with a
        tenancy decorator).  The service *must* already be registered as a
        singleton.

        Args:
            service_type: The registered service type to rebind.
            instance: The replacement singleton instance.
        """
        ...

    @overload
    async def resolve_optional(self, service_type: type[T]) -> T | None: ...

    @overload
    async def resolve_optional(self, service_type: Any) -> Any | None: ...

    async def resolve_optional(self, service_type: Any) -> Any | None:
        """Resolve a service, returning None if not registered.

        This provides a graceful way to handle optional dependencies
        without catching exceptions.

        Args:
            service_type: The type to resolve.

        Returns:
            The resolved instance or None if the service is not registered.
        """
        ...

    @overload
    async def resolve_all(self, service_type: type[T]) -> list[T]: ...

    @overload
    async def resolve_all(self, service_type: Any) -> list[Any]: ...

    async def resolve_all(self, service_type: Any) -> list[Any]:
        """Resolve all registered implementations that are subtypes of a service type.

        Useful for collecting multiple implementations of a protocol or
        abstract base class (e.g. all registered ``EventHandlerProtocol`` instances).

        Args:
            service_type: The base type whose implementations to resolve.

        Returns:
            A list of resolved instances.
        """
        ...


@runtime_checkable
class ContainerValidationProtocol(Protocol):
    """Protocol for container validation methods.

    Development-time validators for detecting configuration issues.
    """

    def validate(self) -> list[str]:
        """Validate the container configuration.

        Checks:
        - All registered services have resolvable dependencies
        - No circular dependencies
        - No scope violations

        Returns:
            List of validation issues (empty if valid).
        """
        ...

    def validate_no_orphans(self) -> list[OrphanedRegistration]:
        """Find registrations that no other service depends on.

        Identifies dead code services registered but never used.

        Returns:
            List of potentially orphaned registrations.
        """
        ...


@runtime_checkable
class BootContainerProtocol(
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
    Protocol,
):
    """Container interface for the provider boot phase.

    During boot, providers need to both resolve existing services (e.g.
    retrieving a raw LLM client) and register new ones (e.g. wrapping
    that client with observability decorators).  This protocol exposes
    exactly those two capabilities without granting access to validation
    or lifecycle methods.

    Any object implementing both :class:`ContainerRegistrarProtocol` and
    :class:`ContainerResolverProtocol` satisfies this protocol via
    structural subtyping.  The concrete :class:`Container` class is the
    primary implementation.
    """


@runtime_checkable
class ContainerProtocol(
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
    ContainerValidationProtocol,
    Protocol,
):
    """Combined DI container protocol covering registration, resolution, and validation.

    Use this instead of ``Any`` when a component needs to both register
    services (via :meth:`singleton`/transient) and resolve them (via
    :meth:`resolve`) within the same method.  This is a structural Protocol
    — any object implementing both :class:`ContainerRegistrarProtocol` and
    :class:`ContainerResolverProtocol` satisfies this type.
    """


__all__ = [
    "BootContainerProtocol",
    "ContainerProtocol",
    "ContainerRegistrarProtocol",
    "ContainerResolverProtocol",
    "ContainerValidationProtocol",
]
