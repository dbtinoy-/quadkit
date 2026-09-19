"""Service store — descriptor storage for the DI container."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from quadkit.di.resolution.descriptor import ServiceDescriptor, ServiceScope
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.types import ServiceFactory

logger = get_logger(__name__)


class ServiceStore:
    """Stores and retrieves service descriptors.

    Owns the descriptor dictionary and provides pure storage operations.
    Does not perform protocol validation or dependency-graph management —
    those concerns belong to ``ServiceRegistry`` and ``GraphValidator``
    respectively.
    """

    def __init__(self) -> None:
        self._descriptors: dict[object, ServiceDescriptor] = {}
        self._named_keys: dict[object, object] = {}

    def _normalize_lookup_key(self, service_type: object) -> object:
        """Translate named type lookups to their registered storage key."""
        if (
            isinstance(service_type, tuple)
            and len(service_type) == 2
            and isinstance(service_type[0], type)
            and isinstance(service_type[1], str)
        ):
            return self._named_keys.get(service_type, service_type)
        if isinstance(service_type, str):
            return self._named_keys.get(service_type, service_type)
        return service_type

    # -- Core CRUD ---------------------------------------------------------

    def add(self, descriptor: ServiceDescriptor) -> None:
        """Store a service descriptor.

        Args:
            descriptor: The descriptor to store. Overwrites any existing
                registration for the same service type.
        """
        self._descriptors[descriptor.service_type] = descriptor

    def get(self, service_type: object) -> ServiceDescriptor | None:
        """Return the descriptor for *service_type*, or ``None`` if absent.

        Args:
            service_type: The registered type or key to look up.

        Returns:
            The matching ``ServiceDescriptor``, or ``None``.
        """
        return self._descriptors.get(self._normalize_lookup_key(service_type))

    def has(self, service_type: object) -> bool:
        """Return ``True`` if *service_type* is registered.

        Args:
            service_type: The type or key to check.
        """
        return self._normalize_lookup_key(service_type) in self._descriptors

    def all(self) -> list[ServiceDescriptor]:
        """Return a snapshot list of all stored descriptors.

        Returns:
            A new list containing every ``ServiceDescriptor`` currently
            in the store. Mutations to the returned list do not affect the
            store.
        """
        return list(self._descriptors.values())

    def clear(self) -> None:
        """Remove all stored descriptors."""
        self._descriptors.clear()
        self._named_keys.clear()

    def update_singleton_instance(self, service_type: object, instance: Any) -> None:
        """Replace the singleton descriptor with a resolved-instance version.

        Called by the resolver after creating a singleton so that future
        resolutions return the cached instance without re-instantiation.

        Args:
            service_type: The registered key of the singleton service.
            instance: The resolved instance to cache.

        Raises:
            KeyError: If *service_type* is not registered.
            ValueError: If the registered service is not a singleton.
        """
        lookup_key = self._normalize_lookup_key(service_type)
        descriptor = self._descriptors.get(lookup_key)
        if descriptor is None:
            raise KeyError(
                f"Cannot update instance: {service_type!r} is not registered",
            )
        if descriptor.scope != ServiceScope.SINGLETON:
            raise ValueError(
                f"Cannot update instance: {service_type!r} is not a singleton",
            )
        self._descriptors[lookup_key] = descriptor.with_instance(instance)

    def is_singleton(self, service_type: object) -> bool:
        """Return ``True`` if *service_type* is registered as a singleton.

        Args:
            service_type: The type or key to check.
        """
        desc = self._descriptors.get(self._normalize_lookup_key(service_type))
        return desc is not None and desc.scope == ServiceScope.SINGLETON

    def add_named_alias(self, service_type: type, name: str, key: object) -> None:
        """Register a typed lookup alias for a named binding."""
        self._named_keys[(service_type, name)] = key
        self._named_keys[name] = key

    # -- Convenience registration helpers ----------------------------------

    def transient(
        self,
        service_type: type,
        factory: ServiceFactory,
        validate: bool = True,  # noqa: ARG002 — kept for API symmetry; protocol validation is handled by ServiceRegistry
    ) -> None:
        """Build and store a transient descriptor.

        Each resolution creates a fresh instance from *factory*.

        Args:
            service_type: The abstract type being registered.
            factory: The callable used to create instances.
            validate: Accepted for API symmetry; protocol validation is
                performed by ``ServiceRegistry``, not the store.
        """
        self.add(
            ServiceDescriptor(
                service_type=service_type,
                implementation=factory,
                scope=ServiceScope.TRANSIENT,
            ),
        )

    def singleton(
        self,
        service_type: type,
        instance: Any | None = None,
        *,
        name: str | None = None,
        factory: ServiceFactory | None = None,
        validate: bool = True,  # noqa: ARG002 — kept for API symmetry; protocol validation is handled by ServiceRegistry
    ) -> None:
        """Build and store a singleton descriptor.

        A single instance is created on first resolution and reused thereafter.

        Args:
            service_type: The class to register as a singleton.
            instance: A pre-built object to use directly, or ``None`` if an
                instance should be created on first resolution.
            name: Optional string key for named singleton registrations.
                Resolve with ``Annotated[T, Named(name)]``.
            factory: Callable used to create the instance when no *instance*
                is provided.
            validate: Accepted for API symmetry; protocol validation is
                performed by ``ServiceRegistry``, not the store.
        """
        key: type | tuple[type, str] = (
            (service_type, name) if name is not None else service_type
        )
        implementation = instance if instance is not None else factory

        if implementation is None:
            implementation = service_type

        is_instantiated = instance is not None and not (
            inspect.isclass(instance)
            or inspect.isfunction(instance)
            or inspect.ismethod(instance)
        )

        self.add(
            ServiceDescriptor(
                service_type=key,
                implementation=implementation,
                scope=ServiceScope.SINGLETON,
                instance=instance if is_instantiated else None,
                is_instantiated=is_instantiated,
            ),
        )
        if name is not None:
            self.add_named_alias(service_type, name, key)

    def scoped(
        self,
        service_type: type,
        factory: ServiceFactory,
        validate: bool = True,  # noqa: ARG002 — kept for API symmetry; protocol validation is handled by ServiceRegistry
        *,
        name: str | None = None,
    ) -> None:
        """Build and store a scoped descriptor.

        One instance is created per active scope (e.g. per HTTP request).

        Args:
            service_type: The abstract type being registered.
            factory: The callable used to create instances within a scope.
            validate: Accepted for API symmetry; protocol validation is
                performed by ``ServiceRegistry``, not the store.
            name: Optional string key for named scoped registration.
                Resolve via ``Annotated[T, Named(name)]``.
        """
        key: type | tuple[type, str] = (
            (service_type, name) if name is not None else service_type
        )
        self.add(
            ServiceDescriptor(
                service_type=key,
                implementation=factory,
                scope=ServiceScope.SCOPED,
            ),
        )
        if name is not None:
            self.add_named_alias(service_type, name, key)


__all__ = ["ServiceStore"]
