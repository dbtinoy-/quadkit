"""Dependency injection container — facade coordinating all DI components."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    overload,
)

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.di.container.container_introspection import ContainerIntrospectionMixin
from quadkit.di.container.container_resolution import ContainerResolutionMixin
from quadkit.di.container.container_runtime import ContainerRuntimeMixin
from quadkit.di.container.registrar import ContainerRegistrarImpl
from quadkit.di.container.resolver import ContainerResolverImpl
from quadkit.di.container.scope import Scope
from quadkit.di.container.validation import ContainerValidator, OrphanedRegistration
from quadkit.di.extensions.interceptors import InterceptorRegistry
from quadkit.di.extensions.validator import ProtocolValidator
from quadkit.di.resolution.diagnostics import ContainerDiagnostics
from quadkit.di.resolution.injector import DependencyInjector
from quadkit.di.resolution.invoker import FunctionInvoker
from quadkit.di.resolution.registry import ServiceRegistry
from quadkit.di.resolution.resolver import ServiceResolver
from quadkit.di.resolution.type_hints import TypeHintResolverImpl
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.resolution.descriptor import ServiceDescriptor
    from quadkit.di.resolution.type_hints import BoundedCache
    from quadkit.di.types import ServiceFactory

T = TypeVar("T")

logger = get_logger(__name__)


class Container(
    ContainerRuntimeMixin,
    ContainerIntrospectionMixin,
    ContainerResolutionMixin,
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
):
    """Dependency injection container.

    Manages service registration, resolution, and lifecycle.
    Delegates to ContainerRegistrarImpl, ContainerResolverImpl, and ContainerValidator
    for write, read, and validation responsibilities respectively.

    Usage::

        container = Container()
        container.singleton(MyService, MyService())
        container.transient(IRepo, SqlRepo)

        service = await container.resolve(MyService)
    """

    _resolver_obj: ContainerResolverImpl

    def __init__(
        self,
        parent: Container | None = None,
        testing_mode: bool = False,
        strict_mode: bool = False,
        validate_on_register: bool = True,
    ) -> None:
        self._parent = parent
        #: Raise on unresolved optional lookups (see :meth:`resolve_optional`).
        self.strict_mode = strict_mode
        #: Default for the ``validate`` argument of registration methods.
        self.validate_on_register = validate_on_register

        # Core resolution infrastructure
        self._type_hint_resolver = TypeHintResolverImpl()
        self._protocol_validator = ProtocolValidator()
        self._registry = ServiceRegistry(
            self._protocol_validator,
            self._type_hint_resolver,
        )
        self._injector = DependencyInjector(self._type_hint_resolver)
        # interceptor support must exist before the resolver is built
        self.interceptor_registry = InterceptorRegistry()
        self._service_resolver = ServiceResolver(
            self._registry,
            self._injector,
            parent._resolver if parent else None,
            interceptor_registry=self.interceptor_registry,
        )
        # Link injector to resolver for recursive resolution
        self._injector.set_resolver(self._service_resolver)

        from quadkit.di.resolution.type_hints import BoundedCache

        # Internal cache for type hints and signatures (MAJ-11)
        self._hints_cache: BoundedCache = BoundedCache(maxsize=1024)

        # Diagnostics component
        self._diagnostics = ContainerDiagnostics(
            self._registry, self._type_hint_resolver
        )
        self._invoker = FunctionInvoker(self._service_resolver, self._hints_cache)  # type: ignore[arg-type]

        # Component facades
        self._registrar = ContainerRegistrarImpl(
            self._registry, testing_mode=testing_mode
        )
        parent_resolver_obj = parent._resolver_obj if parent else None
        self._resolver_obj = ContainerResolverImpl(
            self._registry,
            self._service_resolver,
            self._invoker,
            self._hints_cache,
            scope_factory=lambda: Scope(self),
            parent_resolver=parent_resolver_obj,
        )
        self._validator = ContainerValidator(self._registry, self._type_hint_resolver)

    # -- Component accessors -----------------------------------------------

    @property
    def registrar(self) -> ContainerRegistrarImpl:
        """Return the write-only registrar component."""
        return self._registrar

    @property
    def resolver(self) -> ContainerResolverImpl:
        """Return the read-only resolver component."""
        return self._resolver_obj

    # -- Internal API for Scope --------------------------------------------

    @property
    def _resolver(self) -> ServiceResolver:
        """Internal: Get the service resolver. For Scope and internal use only."""
        return self._service_resolver

    def _get_descriptor(self, service_type: type) -> ServiceDescriptor | None:
        """Internal: Get descriptor for a service type. For Scope use only."""
        return self._registry.get(service_type)

    async def _create_with_injection(
        self,
        implementation: type,
        service_type: type,
    ) -> Any:
        """Internal: Create instance with DI. For Scope use only."""
        return await self._service_resolver.create_with_injection(
            implementation, service_type
        )

    # -- Registration ------------------------------------------------------

    def clear(self) -> None:
        """Clear all registered services.

        Raises:
            ContainerError: if the container has been frozen.
        """
        self._registrar.clear()

    def transient(
        self,
        service_type: type[T],
        factory: ServiceFactory[T],
        validate: bool | None = None,
    ) -> None:
        """Register a transient service (new instance each resolution).

        ``validate=None`` (default) falls back to
        :attr:`validate_on_register`.
        """
        if validate is None:
            validate = self.validate_on_register
        self._registrar.transient(service_type, factory, validate=validate)

    @overload
    def singleton(
        self,
        service_type: type[T],
        instance: T | None = None,
        *,
        name: str | None = None,
        factory: ServiceFactory[T] | None = None,
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

        Pass ``instance`` for a pre-built singleton, or ``factory`` for lazy creation.
        Use ``name`` for named registrations resolvable via ``Annotated[T, Named('...')]]``.
        """
        self._registrar.singleton(
            service_type,
            instance,
            name=name,
            factory=factory,
            validate=validate,
        )

    def scoped(
        self,
        service_type: type[T],
        factory: ServiceFactory[T],
        validate: bool | None = None,
        *,
        name: str | None = None,
    ) -> None:
        """Register a scoped service (instance per scope).

        ``validate=None`` (default) falls back to
        :attr:`validate_on_register`.
        """
        if validate is None:
            validate = self.validate_on_register
        self._registrar.scoped(service_type, factory, validate=validate, name=name)

    @property
    def is_frozen(self) -> bool:
        """Return ``True`` if this container has been frozen.

        Once frozen, no further service registrations are allowed.
        Use this in tests or startup checks to verify container state.
        """
        return self._registrar.is_frozen

    def freeze(self, validate: bool = True) -> None:
        """Prevent any further service registrations on this container.

        After freezing, calls to ``transient()``, ``singleton()``, ``scoped()``
        or ``clear()`` will raise :class:`~quadkit.exceptions.ContainerError`.
        Freezing is intended to be invoked once the registration phase is complete
        (e.g. after ``ProviderOrchestrator.register_all()``).

        Args:
            validate: When ``True`` (default), runs pre-flight dependency
                validation before freezing. Raises
                :class:`~quadkit.contracts.exceptions.container.ContainerValidationError`
                if any missing dependencies, circular references, or scope
                violations are detected.

        Raises:
            ContainerValidationError: If ``validate=True`` and validation issues
                are found.
        """
        if validate:
            from quadkit.contracts.exceptions.container import ContainerValidationError

            issues = self.validate()
            if issues:
                raise ContainerValidationError(issues)
        self._registrar.freeze()


__all__ = ["Container", "OrphanedRegistration", "Scope"]
