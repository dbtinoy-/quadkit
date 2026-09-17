"""DI container registrar — write-only registration phase."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, TypeVar

from quadkit.contracts.exceptions import ContainerError
from quadkit.di.context import get_current_module
from quadkit.di.resolution.registry import ServiceRegistry
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

if TYPE_CHECKING:
    from quadkit.di.types import ServiceFactory

T = TypeVar("T")
logger = get_logger(__name__)


class ContainerRegistrarImpl:
    """Write-only service registration.

    Implements ContainerRegistrarProtocol from quadkit-contracts.
    Used during Provider.register() phase — resolving is not possible here.

    Args:
        registry: The shared service registry.
        testing_mode: If True, allows override() even after freeze.
    """

    def __init__(self, registry: ServiceRegistry, testing_mode: bool = False) -> None:
        self._registry = registry
        self._frozen: bool = False
        self._testing_mode: bool = testing_mode

    @property
    def is_frozen(self) -> bool:
        """Return True if this registrar has been frozen."""
        return self._frozen

    def freeze(self) -> None:
        """Prevent any further service registrations."""
        self._frozen = True

    @contextlib.contextmanager
    def _registration_window(self) -> Iterator[None]:
        """Framework-managed window that reopens registration for the boot phase.

        ``freeze()`` closes registration to user code permanently. Providers
        that materialize services during boot (e.g. ``@provide`` factories)
        bind their products after the container has frozen, which the
        lifecycle manager performs inside this window. The window restores
        the frozen state on exit — including on error — so the freeze
        guarantee outside the boot phase is unchanged.
        """
        was_frozen = self._frozen
        self._frozen = False
        try:
            yield
        finally:
            self._frozen = was_frozen

    def clear(self) -> None:
        """Clear all registered services.

        Raises:
            ContainerError: If the container has been frozen.
        """
        if self._frozen:
            raise ContainerError("Cannot clear services after container is frozen")
        self._registry.clear()

    def transient(
        self,
        service_type: type[T],
        factory: ServiceFactory[T],
        validate: bool = True,
    ) -> None:
        """Register a transient service (new instance each resolution).

        Args:
            service_type: The abstract type (protocol/class) being registered.
            factory: Factory callable or class used to create instances.
            validate: Whether to validate protocol conformance.

        Raises:
            ContainerError: If the container has been frozen.
        """
        if self._frozen:
            raise ContainerError(
                "Cannot register transient service after container is frozen",
            )
        self._registry.transient(service_type, factory, validate=validate)
        self._registry.attribute(service_type, get_current_module())

    def singleton(
        self,
        service_type: type[T],
        instance: T | None = None,
        *,
        name: str | None = None,
        factory: ServiceFactory[T] | None = None,
        validate: bool = True,
    ) -> None:
        """Register a singleton service (shared instance).

        Args:
            service_type: The abstract type (protocol/class) being registered.
            instance: Pre-built singleton instance.
            name: Optional string key for named registrations.
            factory: Factory callable for lazy creation.
            validate: Whether to validate protocol conformance.

        Raises:
            ContainerError: If the container has been frozen.
        """
        if self._frozen:
            raise ContainerError(
                "Cannot register singleton service after container is frozen",
            )
        self._registry.singleton(
            service_type,
            instance,
            name=name,
            factory=factory,
            validate=validate,
        )
        self._registry.attribute(service_type, get_current_module())

    def scoped(
        self,
        service_type: type[T],
        factory: ServiceFactory[T],
        validate: bool = True,
        *,
        name: str | None = None,
    ) -> None:
        """Register a scoped service (instance per scope).

        Args:
            service_type: The abstract type (protocol/class) being registered.
            factory: Factory callable or class used to create instances.
            validate: Whether to validate protocol conformance.
            name: Optional string key for named registrations.

        Raises:
            ContainerError: If the container has been frozen.
        """
        if self._frozen:
            raise ContainerError(
                "Cannot register scoped service after container is frozen",
            )
        self._registry.scoped(service_type, factory, validate=validate, name=name)
        self._registry.attribute(service_type, get_current_module())

    def override(self, service_type: type[T], instance: T) -> None:
        """Replace a service registration for testing purposes.

        Only available on registrars created with testing_mode=True.
        Works even on frozen registrars.

        Args:
            service_type: The service type to override.
            instance: The replacement instance.

        Raises:
            ContainerError: If not in testing mode.
            ContainerError: If the service is not registered.
        """
        if not self._testing_mode:
            raise ContainerError(
                "override() is only available on containers created with "
                "testing_mode=True. Use Container(testing_mode=True) in tests.",
            )
        if not self._registry.has(service_type):
            raise ContainerError(
                f"Cannot override {getattr(service_type, '__name__', repr(service_type))}: "
                "not registered",
            )
        self._registry.update_singleton_instance(service_type, instance)

    def bind(
        self,
        service_type: type[T],
        instance: T,
    ) -> None:
        """Bind a pre-built singleton instance, overwriting any existing binding.

        Works even after freeze — designed for rebinding during boot.
        The service must already be registered as a singleton.
        """
        self._registry.update_singleton_instance(service_type, instance)

    def has(self, service_type: object) -> bool:
        """Check if a service is explicitly registered in this registrar."""
        return self._registry.has(service_type)


__all__ = ["ContainerRegistrarImpl"]
