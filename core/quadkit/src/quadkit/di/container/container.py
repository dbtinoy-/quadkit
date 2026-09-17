"""Dependency injection container — facade coordinating all DI components."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    TypeVar,
    cast,
    get_args,
    get_origin,
    overload,
)

from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.di.container.container_introspection import ContainerIntrospectionMixin
from quadkit.di.container.container_runtime import ContainerRuntimeMixin
from quadkit.di.container.registrar import ContainerRegistrarImpl
from quadkit.di.container.resolver import ContainerResolverImpl
from quadkit.di.container.scope import Scope
from quadkit.di.container.validation import ContainerValidator, OrphanedRegistration
from quadkit.di.context import _module_graph, check_visibility, get_current_module
from quadkit.di.extensions.interceptors import InterceptorRegistry
from quadkit.di.extensions.validator import ProtocolValidator
from quadkit.di.module.errors import format_visibility_error
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
        self.__service_resolver = ServiceResolver(
            self._registry,
            self._injector,
            parent._resolver if parent else None,
            interceptor_registry=self.interceptor_registry,
        )
        # Link injector to resolver for recursive resolution
        self._injector.set_resolver(self.__service_resolver)

        from quadkit.di.resolution.type_hints import BoundedCache

        # Internal cache for type hints and signatures (MAJ-11)
        self._hints_cache: BoundedCache = BoundedCache(maxsize=1024)

        # Diagnostics component
        self._diagnostics = ContainerDiagnostics(
            self._registry, self._type_hint_resolver
        )
        self._invoker = FunctionInvoker(self.__service_resolver, self._hints_cache)  # type: ignore[arg-type]

        # Component facades
        self._registrar = ContainerRegistrarImpl(
            self._registry, testing_mode=testing_mode
        )
        parent_resolver_obj = parent._resolver_obj if parent else None
        self._resolver_obj = ContainerResolverImpl(
            self._registry,
            self.__service_resolver,
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
        return self.__service_resolver

    def _get_descriptor(self, service_type: type) -> ServiceDescriptor | None:
        """Internal: Get descriptor for a service type. For Scope use only."""
        return self._registry.get(service_type)

    async def _create_with_injection(
        self,
        implementation: type,
        service_type: type,
    ) -> Any:
        """Internal: Create instance with DI. For Scope use only."""
        return await self.__service_resolver.create_with_injection(
            implementation, service_type
        )

    # -- Registration ------------------------------------------------------

    # -- Query ---
    # -- Query -------------------------------------------------------------

    def has(self, service_type: object) -> bool:
        """Check if a service is explicitly registered."""
        if self._registry.has(service_type):
            return True
        return self._parent.has(service_type) if self._parent else False

    @overload
    async def resolve_optional(self, service_type: type[T]) -> T | None: ...

    @overload
    async def resolve_optional(self, service_type: Any) -> Any | None: ...

    async def resolve_optional(self, service_type: Any) -> Any | None:
        """Resolve a service, returning None if not registered.

        Provides graceful handling for optional dependencies without
        requiring callers to catch exceptions.

        Args:
            service_type: The type to resolve.

        Returns:
            The resolved instance or None if the service is not registered.
        """
        if self.has(service_type):
            return await self.resolve(service_type)
        if self.strict_mode:
            name = getattr(service_type, "__name__", repr(service_type))
            raise UnresolvableDependencyError(
                f"'{name}' is not registered in the container and "
                "strict_mode is enabled; register it or disable strict mode.",
                dependency=name,
            )
        return None

    @overload
    async def resolve_all(self, service_type: type[T]) -> list[T]: ...

    @overload
    async def resolve_all(self, service_type: Any) -> list[Any]: ...

    async def resolve_all(self, service_type: Any) -> list[Any]:
        """Resolve all registered implementations that are subtypes of a service type.

        Args:
            service_type: The base type whose implementations to resolve.

        Returns:
            A list of resolved instances for matching registrations.
        """
        results: list[Any] = []
        for registered_type in (d.service_type for d in self._registry.all()):
            if isinstance(registered_type, type) and issubclass(
                registered_type,
                service_type,
            ):
                results.append(await self.resolve(registered_type))
        if self._parent:
            results.extend(await self._parent.resolve_all(service_type))
        return results

    def is_singleton(self, service_type: object) -> bool:
        """Check if a service is registered as a singleton."""
        return self._registry.is_singleton(service_type)

    def create_invoker(self) -> FunctionInvoker:
        """Create a :class:`~quadkit.di.resolution.invoker.FunctionInvoker` bound to this container.

        Returns a new invoker that shares this container's service resolver and
        type-hint cache, so repeated calls to :meth:`FunctionInvoker.call` benefit
        from the warm cache without exposing the resolver's private attributes.

        Returns:
            A :class:`~quadkit.di.resolution.invoker.FunctionInvoker` configured
            with this container's resolver and hints cache.

        Example::

            invoker = container.create_invoker()
            result = await invoker.call(my_function)
        """
        return FunctionInvoker(self.__service_resolver, self._hints_cache)  # type: ignore[arg-type]

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

    # -- Resolution --------------------------------------------------------

    @overload
    async def resolve(
        self, service_type: type[T], *, bypass_visibility: bool = False
    ) -> T: ...

    @overload
    async def resolve(
        self, service_type: Any, *, bypass_visibility: bool = False
    ) -> Any: ...

    async def resolve(
        self, service_type: Any, *, bypass_visibility: bool = False
    ) -> Any:
        """Asynchronously resolve a service by its registered type.

        Args:
            service_type: The service type to resolve.
            bypass_visibility: If True, skip module visibility enforcement.
                Use only in framework-internal resolution paths.

        Returns:
            The resolved service instance.

        Raises:
            ModuleVisibilityError: If the current module context does not
                have visibility over the requested service type.
        """
        if not bypass_visibility:
            if not check_visibility(service_type):
                module = get_current_module()
                consumer_name = module.__name__ if module else "unknown"
                graph = _module_graph.get()

                if get_origin(service_type) is Annotated:
                    annotated_args = get_args(service_type)
                    if annotated_args:
                        service_type = annotated_args[0]

                providing_module = self._registry.providing_module(service_type)
                if providing_module is module and module is not None:
                    # Private to the consuming module itself — no
                    # cross-module surface is involved.
                    return await self.__service_resolver.resolve(service_type)

                if (
                    graph is not None
                    and module is not None
                    and hasattr(graph, "find_modules_exporting")
                ):
                    consumer_node = (
                        graph.get_module(module)
                        if hasattr(graph, "get_module")
                        else None
                    )
                    consumer_imports = [
                        imported.__name__
                        for imported in getattr(consumer_node, "imports", [])
                    ]
                    exporting_nodes = graph.find_modules_exporting(service_type)
                    exporting_names = [node.name for node in exporting_nodes]

                    if not exporting_names:
                        if providing_module is None:
                            # Not registered through any module and not
                            # exported anywhere — a standalone or framework
                            # service, outside the module surface.
                            return await self.__service_resolver.resolve(service_type)
                        providing_name = getattr(
                            providing_module, "__name__", "its provider module"
                        )
                        message = (
                            f"Module '{consumer_name}' cannot resolve "
                            f"'{service_type.__name__}': provided by "
                            f"'{providing_name}' but not exported by it"
                        )
                        hint = (
                            f"Export {service_type.__name__} from "
                            f"'{providing_name}', or provide it from a "
                            "global module."
                        )
                    else:
                        exported_types = sorted(
                            {
                                export.__name__
                                for node in exporting_nodes
                                for export in getattr(node, "exports", [])
                            }
                        )
                        message = format_visibility_error(
                            consumer_module=consumer_name,
                            consumer_provider=consumer_name,
                            provider_module=exporting_names,
                            service_type=service_type.__name__,
                            exported_types=exported_types,
                            consumer_imports=consumer_imports,
                        )
                        hint = (
                            f"Import one of {exporting_names} "
                            f"into {consumer_name}, or make it global."
                        )
                else:
                    message = (
                        f"Module '{consumer_name}' cannot resolve "
                        f"'{service_type.__name__}': not in its exports or global scope"
                    )
                    hint = "Import the module that exports this service, or make it global."

                raise ModuleVisibilityError(
                    message,
                    consumer_module=consumer_name,
                    service_type=service_type.__name__,
                    hint=hint,
                )
        return await self.__service_resolver.resolve(service_type)

    def resolve_sync(self, service_type: type[T]) -> T:
        """Synchronously resolve an already-instantiated singleton.

        This is intended for use in decorators or other synchronous contexts
        where async resolution is not possible. It ONLY works for singletons
        that have already been instantiated (e.g. during boot).

        Args:
            service_type: The service type to resolve.

        Returns:
            The resolved instance.

        Raises:
            UnresolvableDependencyError: If not a singleton or not instantiated.
        """
        descriptor = self._registry.get(service_type)
        if descriptor is not None and descriptor.is_instantiated:
            return cast("T", descriptor.instance)

        if self._parent:
            return self._parent.resolve_sync(service_type)

        from quadkit.contracts.exceptions import UnresolvableDependencyError

        raise UnresolvableDependencyError(
            f"Cannot resolve {service_type} synchronously: "
            "not an instantiated singleton."
        )

    # -- Validation ----------------------------------------------------------

    # -- Scoping -----------------------------------------------------------


__all__ = ["Container", "OrphanedRegistration", "Scope"]
