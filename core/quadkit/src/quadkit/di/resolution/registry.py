"""Service registry for dependency injection container.

``ServiceRegistry`` is a thin facade that delegates descriptor storage to
``ServiceStore`` and dependency-graph validation to ``GraphValidator``.
The public API is identical to the original monolithic implementation so
all existing callers continue to work without modification.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from quadkit.di.resolution.descriptor import ServiceDescriptor, ServiceScope
from quadkit.di.resolution.store import ServiceStore
from quadkit.di.resolution.validator import GraphValidator

if TYPE_CHECKING:
    from quadkit.di.protocols import (
        ProtocolValidatorProtocol,
        TypeHintResolverProtocol,
    )
    from quadkit.di.types import ServiceFactory


class ServiceRegistry:
    """Thin facade over ServiceStore and GraphValidator.

    Provides the canonical registration API used throughout the container
    while delegating storage to :class:`ServiceStore` and cycle/graph
    validation to :class:`GraphValidator`.
    """

    def __init__(
        self,
        protocol_validator: ProtocolValidatorProtocol | None = None,
        type_hint_resolver: TypeHintResolverProtocol | None = None,
    ) -> None:
        self._protocol_validator = protocol_validator
        self._type_hint_resolver = type_hint_resolver
        self._store = ServiceStore()
        self._validator = GraphValidator(self._store, type_hint_resolver)
        self._attribution: dict[type, type] = {}

    # -- Store access ------------------------------------------------------

    @property
    def store(self) -> ServiceStore:
        """The underlying descriptor store."""
        return self._store

    # -- Module attribution ------------------------------------------------

    def attribute(self, service_type: type, module_class: type | None) -> None:
        """Record the module whose provider registered *service_type*.

        Called at registration time with the active module context, if any.
        Standalone and framework registrations leave no attribution, which
        the visibility gate treats as unrestricted.
        """
        if module_class is not None:
            self._attribution[service_type] = module_class

    def providing_module(self, service_type: type) -> type | None:
        """Return the module that registered *service_type*, or ``None``."""
        return self._attribution.get(service_type)

    # -- Core operations ---------------------------------------------------

    def add(self, descriptor: ServiceDescriptor, validate: bool = True) -> None:
        """Add a service descriptor.

        Args:
            descriptor: Service descriptor to add.
            validate: Whether to perform registration-time cycle detection.
        """
        self._store.add(descriptor)
        self._validator.update_for_descriptor(descriptor)
        if validate:
            self._validator._check_eager_cycle(descriptor.service_type)

    def get(self, service_type: object) -> ServiceDescriptor | None:
        """Return a descriptor by type, or ``None`` if absent."""
        return self._store.get(service_type)

    def has(self, service_type: object) -> bool:
        """Return ``True`` if *service_type* is registered."""
        return self._store.has(service_type)

    def all(self) -> list[ServiceDescriptor]:
        """Return all stored descriptors."""
        return self._store.all()

    def clear(self) -> None:
        """Remove all registrations and clear the dependency graph."""
        self._store.clear()
        self._validator.clear()

    def update_singleton_instance(self, service_type: object, instance: Any) -> None:
        """Update a singleton descriptor with its created instance.

        Called by ServiceResolver after creating a singleton instance.
        Keeps encapsulation — resolver doesn't touch _descriptors directly.
        """
        self._store.update_singleton_instance(service_type, instance)

    # -- Registration helpers ----------------------------------------------

    def transient(
        self,
        service_type: type,
        factory: ServiceFactory,
        validate: bool = True,
    ) -> None:
        """Register a transient service."""
        if validate:
            self._validate_registration(service_type, factory)
        self.add(
            ServiceDescriptor(
                service_type=service_type,
                implementation=factory,
                scope=ServiceScope.TRANSIENT,
            ),
            validate=validate,
        )

    def singleton(
        self,
        service_type: type,
        instance: Any | None = None,
        *,
        name: str | None = None,
        factory: ServiceFactory | None = None,
        validate: bool = True,
    ) -> None:
        """Register a singleton service.

        Args:
            service_type: The class to register as a singleton.
            instance: If a live object, stored as the singleton instance.
            name: Optional string key for named registrations.
            factory: If provided, used as the factory to create the instance.
            validate: Whether to perform registration-time validation.
        """
        key: type | tuple[type, str] = (
            (service_type, name) if name is not None else service_type
        )
        implementation = instance if instance is not None else factory

        if validate and inspect.isclass(service_type) and implementation is not None:
            self._validate_registration(service_type, implementation)

        if implementation is None:
            implementation = service_type

        # Pre-built instances are returned directly by the resolver without calling
        # them as a factory. A class or callable passed as `instance` (unusual but
        # valid) must still be treated as a factory, so we exclude those here.
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
            validate=validate and inspect.isclass(service_type),
        )
        if name is not None:
            self._store.add_named_alias(service_type, name, key)

    def scoped(
        self,
        service_type: type,
        factory: ServiceFactory,
        validate: bool = True,
        *,
        name: str | None = None,
    ) -> None:
        """Register a scoped service.

        Args:
            service_type: The abstract type being registered.
            factory: Factory callable, called once per scope.
            validate: Whether to perform registration-time validation.
            name: Optional string key for named scoped registration.
                Resolve via ``Annotated[T, Named(name)]``.
        """
        key: type | tuple[type, str] = (
            (service_type, name) if name is not None else service_type
        )
        if validate and inspect.isclass(service_type):
            self._validate_registration(service_type, factory)
        self.add(
            ServiceDescriptor(
                service_type=key,
                implementation=factory,
                scope=ServiceScope.SCOPED,
            ),
            validate=validate and inspect.isclass(service_type),
        )
        if name is not None:
            self._store.add_named_alias(service_type, name, key)

    def is_singleton(self, service_type: object) -> bool:
        """Return ``True`` if *service_type* is registered as a singleton."""
        return self._store.is_singleton(service_type)

    def validate_graph(self) -> list[str]:
        """Validate the entire dependency graph.

        Checks for:
        - Missing dependencies (registered but needs something unregistered)
        - Circular dependencies across any path

        Returns:
            List of error messages (empty if valid).
        """
        return self._validator.validate_graph()

    # -- Validation --------------------------------------------------------

    def _validate_registration(self, service_type: object, implementation: Any) -> None:
        """Validate that *implementation* satisfies the protocol if applicable."""
        if not self._protocol_validator:
            return

        from quadkit.contracts.exceptions import (
            ProtocolValidationError,
            RegistrationError,
        )

        try:
            self._protocol_validator.validate_registration(service_type, implementation)  # type: ignore[arg-type]
        except ProtocolValidationError as exc:
            raise RegistrationError(str(exc)) from exc


__all__ = ["ServiceRegistry"]
