"""Container builder for fluent API container construction.

Provides a declarative, chainable API for building DI containers
outside the ``Application`` lifecycle.  Primarily used for testing
and programmatic container construction.

For application-level composition, use
:class:`~quadkit.app.base.Application` with :meth:`add_module`
and :meth:`add_provider` instead.

Example::

    container = await (
        ContainerBuilder()
        .add_singleton(DatabaseConfig, lambda: db_config)
        .add_scoped(UserRepository, SQLAlchemyUserRepository)
        .add_transient(UserService, UserService)
        .build()
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from quadkit.contracts import ServiceScope
from quadkit.contracts.exceptions import ContainerBuildError, QuadkitError
from quadkit.di.container import Container
from quadkit.di.module import (
    DynamicModule,
    get_module_metadata,
    is_dynamic_module,
    is_module,
)
from quadkit.logging import get_logger
from quadkit.primitives.builder import AbstractBuilder

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core.di import ContainerResolverProtocol

logger = get_logger(__name__)

T = TypeVar("T")


class ServiceRegistration:
    """Represents a service registration."""

    def __init__(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T],
        scope: ServiceScope,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize a service registration.

        Args:
            interface: The service interface/contract.
            implementation: The concrete implementation or factory.
            scope: The service lifetime scope.
            metadata: Optional metadata for the service.
        """
        self.interface = interface
        self.implementation = implementation
        self.scope = scope
        self.metadata = metadata or {}


class ContainerBuilder(AbstractBuilder[Container]):
    """Fluent API for building DI containers.

    This builder provides a clean, declarative way to configure services
    and their dependencies for **testing** and **programmatic** container
    construction.

    For application-level composition, use
    :class:`~quadkit.app.base.Application` instead — it provides the
    full lifecycle (register → freeze → validate → boot → shutdown) and
    module compilation.

    Example::

        container = await (
            ContainerBuilder()
            .add_singleton(DatabaseConfig, lambda: db_config)
            .add_scoped(UserRepository, SQLAlchemyUserRepository)
            .add_transient(UserService, UserService)
            .build()
        )
    """

    def __init__(self) -> None:
        """Initialize the container builder."""
        super().__init__()
        self._registrations: list[ServiceRegistration] = []
        self._modules: list[type | DynamicModule] = []
        self._providers: list[Any] = []
        self._validation_enabled = True

    def add_singleton(
        self,
        interface: type[T],
        implementation: type[T] | Callable[[], T],
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        """Register a singleton service.

        Args:
            interface: The service interface/contract.
            implementation: The concrete class or factory function.
            metadata: Optional metadata.

        Returns:
            Self for method chaining.
        """
        self._registrations.append(
            ServiceRegistration(
                interface=interface,
                implementation=implementation,
                scope=ServiceScope.SINGLETON,
                metadata=metadata,
            ),
        )
        return self

    def add_instance(
        self,
        interface: type[T],
        instance: T,
    ) -> Self:
        """Register a pre-built instance as a singleton.

        Args:
            interface: The service interface/contract.
            instance: The pre-built instance.

        Returns:
            Self for method chaining.
        """
        self._registrations.append(
            ServiceRegistration(
                interface=interface,
                implementation=lambda: instance,
                scope=ServiceScope.SINGLETON,
            ),
        )
        return self

    def add_scoped(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T],
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        """Register a scoped service.

        Args:
            interface: The service interface/contract.
            implementation: The concrete class or factory function.
            metadata: Optional metadata.

        Returns:
            Self for method chaining.
        """
        self._registrations.append(
            ServiceRegistration(
                interface=interface,
                implementation=implementation,
                scope=ServiceScope.SCOPED,
                metadata=metadata,
            ),
        )
        return self

    def add_transient(
        self,
        interface: type[T],
        implementation: type[T] | Callable[..., T],
        metadata: dict[str, Any] | None = None,
    ) -> Self:
        """Register a transient service.

        Args:
            interface: The service interface/contract.
            implementation: The concrete class or factory function.
            metadata: Optional metadata.

        Returns:
            Self for method chaining.
        """
        self._registrations.append(
            ServiceRegistration(
                interface=interface,
                implementation=implementation,
                scope=ServiceScope.TRANSIENT,
                metadata=metadata,
            ),
        )
        return self

    def add_module(self, module_or_dynamic: type | DynamicModule) -> Self:
        """Add a module to configure the container.

        Accepts module classes (decorated with ``@module``) and
        :class:`DynamicModule` instances.

        Module providers are registered during :meth:`build`.  The
        builder performs basic module processing (provider extraction)
        but does NOT run the full ``ModuleCompiler`` — it does not
        validate import/export visibility.  For full module validation,
        use :class:`~quadkit.app.base.Application`.

        Args:
            module_or_dynamic: A module class or DynamicModule.

        Returns:
            Self for method chaining.
        """
        self._modules.append(module_or_dynamic)
        return self

    def add_provider(self, provider: Any) -> Self:
        """Add a provider whose ``register()`` will be called during build.

        Args:
            provider: A Provider instance.

        Returns:
            Self for method chaining.
        """
        self._providers.append(provider)
        return self

    def disable_validation(self) -> Self:
        """Disable container validation during build.

        Returns:
            Self for method chaining.
        """
        self._validation_enabled = False
        return self

    async def build(self) -> ContainerResolverProtocol:  # type: ignore[override]
        """Build and validate the container.

        Processing order:
            1. Extract providers from modules
            2. Register module providers
            3. Apply direct service registrations
            4. Call ``provider.register()`` on standalone providers
            5. Validate (if enabled)

        Returns:
            A ContainerResolverProtocol for resolving services.

        Raises:
            ContainerBuildError: If build or validation fails.
        """
        container = Container()

        try:
            # 1. Process modules → extract and register their providers
            await self._process_modules(container)

            # 2. Apply direct registrations
            for registration in self._registrations:
                self._apply_registration(container, registration)

            # 3. Register standalone providers
            for provider in self._providers:
                if hasattr(provider, "register"):
                    await provider.register(container)

            # 4. Validate
            if self._validation_enabled:
                self._validate_container(container)

            logger.info(
                "container.built",
                registrations=len(self._registrations),
                modules=len(self._modules),
                providers=len(self._providers),
            )

            return container

        except ContainerBuildError:
            raise
        except (
            RuntimeError,
            TypeError,
            ValueError,
            AttributeError,
            ImportError,
            OSError,
            QuadkitError,
        ) as e:
            logger.exception(
                "container.build_failed",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise ContainerBuildError(f"Container build failed: {e}") from e
        except Exception as e:  # defensive boundary for unexpected third-party failures
            # Defensive boundary for unexpected third-party failures.
            logger.exception(
                "container.build_failed.unexpected",
                error_type=type(e).__name__,
                error=str(e),
            )
            raise ContainerBuildError(
                f"Container build failed with unexpected error type {type(e).__name__}: {e}",
            ) from e

    # -- Private -----------------------------------------------------------

    async def _process_modules(self, container: Container) -> None:
        """Extract providers from modules and register them."""
        visited: set[type] = set()

        for entry in self._modules:
            await self._register_module_providers(entry, container, visited)

    async def _register_module_providers(
        self,
        entry: type | DynamicModule,
        container: Container,
        visited: set[type],
    ) -> None:
        """Recursively extract and register providers from a module."""
        if is_dynamic_module(entry):
            dynamic: DynamicModule = entry  # type: ignore[assignment]
            module_class = dynamic.module
            if module_class in visited:
                return
            visited.add(module_class)

            # Process imports first
            for imp in dynamic.imports:
                await self._register_module_providers(imp, container, visited)

            # Register providers
            for provider_entry in dynamic.providers:
                if hasattr(provider_entry, "register"):
                    # Already an instance
                    await provider_entry.register(container)
                elif isinstance(provider_entry, type):
                    # Class — instantiate and register
                    instance = provider_entry()
                    await instance.register(container)

        elif isinstance(entry, type) and is_module(entry):
            if entry in visited:
                return
            visited.add(entry)

            meta = get_module_metadata(entry)
            if meta is None:
                return

            # Process imports first
            for imp in meta.imports:
                await self._register_module_providers(imp, container, visited)

            # Register providers
            for provider_cls in meta.providers:
                if isinstance(provider_cls, type):
                    instance = provider_cls()
                    if hasattr(instance, "register"):
                        await instance.register(container)

        else:
            logger.warning(
                "container_builder.invalid_module",
                module=repr(entry),
            )

    def _apply_registration(
        self,
        container: Container,
        registration: ServiceRegistration,
    ) -> None:
        """Apply a service registration to the container."""
        if registration.scope == ServiceScope.SINGLETON:
            container.singleton(registration.interface, registration.implementation)
        elif registration.scope == ServiceScope.SCOPED:
            container.scoped(registration.interface, registration.implementation)
        elif registration.scope == ServiceScope.TRANSIENT:
            container.transient(registration.interface, registration.implementation)

    def _validate_container(self, container: Container) -> None:
        """Validate the container configuration.

        Raises:
            ContainerBuildError: If validation fails.
        """
        errors: list[str] = []
        for registration in self._registrations:
            try:
                # Statically unreachable (implementations are callables by
                # type), but kept as a runtime guard against misuse.
                # Cast to object so the callable() guard stays live for mypy.
                impl = cast("object", registration.implementation)
                if not callable(impl):
                    errors.append(
                        f"Invalid implementation for "
                        f"{registration.interface}: "
                        f"{registration.implementation}",
                    )
            except Exception as e:  # noqa: BLE001 — validation must collect, not crash, on odd implementations
                errors.append(
                    f"Failed to validate {registration.interface}: {e}",
                )

        if errors:
            raise ContainerBuildError(
                f"Container validation failed: {errors}",
            )


__all__ = ["ContainerBuilder", "ServiceRegistration"]
