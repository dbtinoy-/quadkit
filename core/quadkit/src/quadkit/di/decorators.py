"""Dependency injection decorators for Quadkit Framework.

Provides decorators for service registration and automatic dependency
injection. DI decorators belong here alongside the DI container system.

Example::

    from quadkit.di import injectable, singleton, inject

    @singleton
    class ConfigService:
        def __init__(self) -> None:
            self.settings = load_settings()

    @injectable
    class UserService:
        def __init__(self, config: ConfigService) -> None:
            self.config = config

    @inject
    async def handle_request(user_svc: UserService) -> None:
        # user_svc is automatically resolved from the container
        ...
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
import inspect
from typing import Any, TypeVar, cast

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.provider import Provider

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])

# Attribute name constants — used for introspection and plugin discovery.
INJECTABLE_ATTR: str = "__quadkit_injectable__"
INJECT_ATTR: str = "__quadkit_inject__"
SCOPE_ATTR: str = "__quadkit_scope__"
PROVIDER_ATTR: str = "__quadkit_provider__"


class Injectable:
    """Decorator class to mark a class as injectable for dependency injection.

    This decorator marks classes for automatic registration with the
    dependency injection container. The container can then resolve
    these services and automatically inject their dependencies.

    Args:
        scope: The service scope — transient (new instance each time),
            singleton (shared instance), or scoped (instance per scope).
            Defaults to transient.
        name: Optional name for the service registration. If not provided,
            the class name is used.
    """

    def __init__(
        self,
        scope: ServiceScope = ServiceScope.TRANSIENT,
        name: str | None = None,
    ) -> None:
        """Initialize the Injectable decorator.

        Args:
            scope: The service scope for this class.
            name: Optional name for the service.
        """
        self.scope = scope
        self.name = name

    def __call__(self, cls: type[T]) -> type[T]:
        """Apply the injectable marker to a class.

        Args:
            cls: The class to mark as injectable.

        Returns:
            The decorated class with injectable metadata attached.
        """
        cast("Any", cls).__quadkit_injectable__ = {
            "scope": self.scope,
            "name": self.name,
        }
        return cls


def injectable(
    scope_or_cls: ServiceScope | type[T] = ServiceScope.TRANSIENT,
    name: str | None = None,
    *,
    scope: ServiceScope | None = None,
) -> Callable[[type[T]], type[T]] | type[T]:
    """Decorator to mark a class as injectable.

    The ``scope`` metadata is honored where a descriptor is created for the
    class: by ``discover_injectables()`` (module scanning) and by explicit
    Provider registration. Resolving the class directly from a bare
    ``Container`` without either step is not supported — the container only
    auto-wires classes carrying ``@inject``-style constructor markers and
    raises ``QK_ERR_DI_004`` otherwise.

    Args:
        scope_or_cls: The service scope or the class if used without parens.
        name: Optional name for the service registration.
        scope: Explicit scope (keyword-only alternative to scope_or_cls).

    Returns:
        The decorator function or the decorated class.
    """
    actual_scope = scope or (
        scope_or_cls
        if isinstance(scope_or_cls, ServiceScope)
        else ServiceScope.TRANSIENT
    )

    if isinstance(scope_or_cls, type):
        return Injectable(scope=ServiceScope.TRANSIENT)(scope_or_cls)

    def decorator(cls: type[T]) -> type[T]:
        return Injectable(scope=actual_scope, name=name)(cls)

    return decorator


def singleton(cls: type[T]) -> type[T]:
    """Decorator to register a class as a singleton service.

    A singleton service is created once and shared across all resolutions.

    Args:
        cls: The class to register as a singleton.

    Returns:
        The decorated class marked for singleton registration.
    """
    return Injectable(scope=ServiceScope.SINGLETON)(cls)


def scoped(cls: type[T]) -> type[T]:
    """Decorator to register a class as a scoped service.

    A scoped service creates one instance per scope (e.g., per request).

    Args:
        cls: The class to register as scoped.

    Returns:
        The decorated class marked for scoped registration.
    """
    return Injectable(scope=ServiceScope.SCOPED)(cls)


def transient(cls: type[T]) -> type[T]:
    """Decorator to register a class as a transient service.

    A transient service creates a new instance each time it is resolved.

    Args:
        cls: The class to register as transient.

    Returns:
        The decorated class marked for transient registration.
    """
    return Injectable(scope=ServiceScope.TRANSIENT)(cls)


def inject(func_or_cls: Any) -> Any:
    """Decorator to enable automatic dependency injection.

    Applied to a class: marks the class for constructor injection.
    Applied to an async function: wraps it to resolve missing arguments
    from the current DI container when invoked via ``container.call()``.

    Args:
        func_or_cls: The class or async function to decorate.

    Returns:
        The decorated class or function with automatic DI support.

    Raises:
        TypeError: If applied to a synchronous (non-async) function.
    """
    if inspect.isclass(func_or_cls):
        cast("Any", func_or_cls).__quadkit_inject__ = True
        return func_or_cls

    if not inspect.iscoroutinefunction(func_or_cls):
        msg = (
            f"@inject decorator requires async functions. "
            f"Make {func_or_cls.__name__} async or use manual DI resolution."
        )
        raise TypeError(msg)

    @wraps(func_or_cls)
    async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            "@inject decorated functions must be invoked via "
            "container.call() or Invoker.invoke() with an explicit container.",
        )

    return async_wrapper


def provider(
    name: str | None = None,
    priority: ProviderPriority = ProviderPriority.NORMAL,
    dependencies: tuple[str, ...] = (),
) -> Callable[[T], T]:
    """Class decorator that configures a :class:`~quadkit.di.provider.Provider`.

    Args:
        name: Optional provider name; if omitted the base class logic will
            generate one based on the class name.
        priority: Initialization priority hint allowing the orchestrator to
            order provider boot. Defaults to ``ProviderPriority.NORMAL``.
        dependencies: Names of other providers that must be booted before
            this one.

    Returns:
        Decorator that configures the provider class in-place.
    """

    def decorator(cls: T) -> T:
        if not issubclass(cls, Provider):  # type: ignore[arg-type]
            cls_name = getattr(cls, "__name__", str(cls))
            raise TypeError(f"{cls_name} must extend Provider")

        original_init = cls.__init__  # type: ignore[misc]

        @wraps(original_init)
        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            original_init(self, *args, **kwargs)
            if name:
                self.name = name
            self.priority = priority
            self.dependencies = tuple(dependencies)

        cls.__init__ = new_init  # type: ignore[misc]
        return cls

    return decorator


__all__ = [
    "INJECTABLE_ATTR",
    "INJECT_ATTR",
    "PROVIDER_ATTR",
    "SCOPE_ATTR",
    "Injectable",
    "inject",
    "injectable",
    "provider",
    "scoped",
    "singleton",
    "transient",
]
