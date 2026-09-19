"""Module decorators — @module, @global_module, create_module."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar, overload

from quadkit.di.module.base import Module
from quadkit.di.module.constants import MODULE_METADATA_ATTR
from quadkit.di.module.metadata import ModuleMetadata
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.module.dynamic import DynamicModule

logger = get_logger(__name__)
T = TypeVar("T")


@overload
def module(
    cls: type[T],
    *,
    name: str | None = ...,
    providers: list[Any] | None = ...,
    imports: list[type | DynamicModule] | None = ...,
    exports: list[type] | None = ...,
    controllers: list[type] | None = ...,
    is_global: bool = ...,
    scan: list[str] | None = ...,
    require_stub: bool = ...,
) -> type[T]: ...


@overload
def module(
    cls: None = ...,
    *,
    name: str | None = ...,
    providers: list[Any] | None = ...,
    imports: list[type | DynamicModule] | None = ...,
    exports: list[type] | None = ...,
    controllers: list[type] | None = ...,
    is_global: bool = ...,
    scan: list[str] | None = ...,
    require_stub: bool = ...,
) -> Callable[[type[T]], type[T]]: ...


def module(
    cls: type[T] | None = None,
    *,
    name: str | None = None,
    providers: list[Any] | None = None,
    imports: list[type | DynamicModule] | None = None,
    exports: list[type] | None = None,
    controllers: list[type] | None = None,
    is_global: bool = False,
    scan: list[str] | None = None,
    require_stub: bool = False,
) -> type[T] | Any:
    """Declare a class as a Quadkit module.

    Supports three usage patterns:

    1. **Bare decorator** — reads ``ClassVar`` defaults from the
       :class:`Module` base class::

        @module
        class MyModule(Module):
            providers = [FooProvider]

    2. **Factory decorator** — explicit arguments::

        @module(providers=[FooProvider], exports=[FooService])
        class MyModule:
            pass

    3. **Combined** — decorator arguments override ``ClassVar`` defaults::

        @module(exports=[FooService])
        class MyModule(Module):
            providers = [FooProvider]       # from ClassVar
            imports   = [ConfigModule]      # from ClassVar

    The ``scan`` parameter enables auto-discovery of ``@injectable`` /
    ``@singleton`` decorated classes in the specified packages::

        @module(scan=["my_app.domain"], exports=[UserServiceProtocol])
        class DomainModule:
            pass

    Args:
        cls: The class being decorated (only when used as a bare decorator).
        name: Optional override for the module name (defaults to class name).
        providers: Provider classes encompassed by this module.
        imports: Module classes or :class:`DynamicModule` descriptors this
            module depends on.
        exports: Contract types visible to importing modules.
        controllers: Controller classes registered with the web layer.
        is_global: If ``True``, exports are visible to all modules without
            explicit import.
        scan: Package paths to scan for ``@injectable`` / ``@singleton``
            classes.
        require_stub: If ``True``, this module requires a stub (test double)
            in test environments.  The ``ModuleCompiler`` will warn or error
            when this module is used without a corresponding stub registered.
    """

    def decorator(actual_cls: type[T]) -> type[T]:
        return _attach_metadata(
            actual_cls,
            name=name,
            providers=providers,
            imports=imports,
            exports=exports,
            controllers=controllers,
            is_global=is_global,
            scan=scan,
            require_stub=require_stub,
        )

    if cls is not None:
        return decorator(cls)
    return decorator


def global_module(cls: type[T]) -> type[T]:
    """Shorthand: ``@global_module`` equals ``@module(is_global=True)``.

    A global module's exports are visible to **all** modules without
    explicit import.  Typical candidates: configuration, logging,
    serialization.

    Example::

        @global_module
        class ConfigModule(Module):
            providers = [ConfigProvider]
            exports   = [ConfigProtocol]
    """
    return _attach_metadata(cls, is_global=True)


def create_module(
    name: str | None = None,
    *,
    providers: list[type] | None = None,
    imports: list[type | DynamicModule] | None = None,
    exports: list[type] | None = None,
    controllers: list[type] | None = None,
    is_global: bool = False,
    scan: list[str] | None = None,
    require_stub: bool = False,
) -> Any:
    """Create a module via a decorator — convenience alias for :func:`module`."""
    return module(
        name=name,
        providers=providers,
        imports=imports,
        exports=exports,
        controllers=controllers,
        is_global=is_global,
        scan=scan,
        require_stub=require_stub,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _attach_metadata(
    cls: type[T],
    *,
    name: str | None = None,
    providers: list[type] | None = None,
    imports: list[type | DynamicModule] | None = None,
    exports: list[type] | None = None,
    controllers: list[type] | None = None,
    is_global: bool = False,
    scan: list[str] | None = None,
    require_stub: bool = False,
) -> type[T]:
    """Attach :class:`ModuleMetadata` to a class.

    Reads ``ClassVar`` defaults from the class hierarchy (if it extends
    :class:`Module`), merges with explicit decorator arguments (decorator
    arguments win), validates, and stores the result as
    ``cls.__quadkit_module__``.

    When ``scan`` is provided, discovers ``@injectable`` / ``@singleton``
    classes in those packages and generates a synthetic provider that
    registers them during boot.
    """
    cls_name: str | None = _read_classvar(cls, "name", None)
    cls_providers: list[type] = _read_classvar(cls, "providers", [])
    cls_imports: list[type] = _read_classvar(cls, "imports", [])
    cls_exports: list[type] = _read_classvar(cls, "exports", [])
    cls_controllers: list[type] = _read_classvar(cls, "controllers", [])
    cls_is_global: bool = _read_classvar(cls, "is_global", False)
    cls_scan: list[str] = _read_classvar(cls, "scan", [])

    resolved_name = name or cls_name or cls.__name__
    resolved_providers: list[Any] = (
        list(providers) if providers is not None else list(cls_providers)
    )
    resolved_imports: list[Any] = (
        list(imports) if imports is not None else list(cls_imports)
    )
    resolved_exports: list[Any] = (
        list(exports) if exports is not None else list(cls_exports)
    )
    resolved_controllers = list(
        controllers if controllers is not None else cls_controllers
    )
    resolved_is_global = is_global or cls_is_global
    resolved_scan = list(scan if scan is not None else cls_scan)

    # Auto-discover injectables from scanned packages
    if resolved_scan:
        from quadkit.app.discovery import discover_injectables

        injectables = discover_injectables(resolved_scan)
        if injectables:
            auto_provider_cls = _create_scan_provider(resolved_name, injectables)
            resolved_providers = [*resolved_providers, auto_provider_cls]

    metadata = ModuleMetadata(
        name=resolved_name,
        providers=resolved_providers,
        imports=resolved_imports,
        exports=resolved_exports,
        controllers=resolved_controllers,
        is_global=resolved_is_global,
        scan=resolved_scan,
        require_stub=require_stub,
    )

    setattr(cls, MODULE_METADATA_ATTR, metadata)
    metadata.__quadkit_owner__ = cls

    # Check that each import class is decorated with @module.
    # (This is a decorator-time check; direct ModuleMetadata() construction
    # skips it so compiler tests can inject arbitrary imports.)
    for i, imp in enumerate(resolved_imports):
        from quadkit.di.module.dynamic import DynamicModule

        if isinstance(imp, DynamicModule):
            continue
        if isinstance(imp, type) and not hasattr(imp, MODULE_METADATA_ATTR):
            raise TypeError(
                f"Module '{resolved_name}': imports[{i}] ({imp.__name__!r}) is "
                f"not decorated with @module. "
                f"Only @module-decorated classes can be imported.",
            )

    logger.debug(
        "module_decorated",
        module=resolved_name,
        providers=len(resolved_providers),
        imports=len(resolved_imports),
        exports=len(resolved_exports),
        controllers=len(resolved_controllers),
        is_global=resolved_is_global,
    )

    return cls


def _read_classvar(cls: type, attr: str, default: Any) -> Any:
    """Read a ClassVar from *cls*, skipping :class:`Module` base defaults.

    Checks ``cls.__dict__`` first, then walks the MRO — skipping
    :class:`Module` and ``object`` — to find inherited values from
    intermediate base classes.
    """
    if attr in cls.__dict__:
        return cls.__dict__[attr]

    for parent in cls.__mro__[1:]:
        if parent is Module or parent is object:
            continue
        if attr in parent.__dict__:
            return parent.__dict__[attr]

    return default


def _create_scan_provider(
    module_name: str,
    injectables: list[tuple[type, Any]],
) -> type:
    """Create a synthetic provider class for auto-discovered injectables.

    Returns a unique Provider subclass (not an instance) that registers
    discovered ``@injectable`` / ``@singleton`` classes into the container.
    The compiler expects provider *classes* in the metadata, so we
    dynamically create a class that stores the injectable list.

    Args:
        module_name: Name of the owning module (used for provider naming).
        injectables: Pairs of ``(class, scope)`` from ``discover_injectables()``.

    Returns:
        A ``Provider`` subclass ready for inclusion in the module's provider list.
    """
    from quadkit.app import InjectableAutoProvider

    # Create a unique subclass so each module gets its own scan provider
    provider_cls = type(
        f"_ScanProvider_{module_name}",
        (InjectableAutoProvider,),
        {},
    )

    # Override __init__ to inject the discovered injectables
    captured_injectables = list(injectables)

    original_init = InjectableAutoProvider.__init__

    def __init__(self: Any) -> None:  # noqa: N807
        original_init(self, captured_injectables)
        self.name = f"_scan_{module_name}"

    provider_cls.__init__ = __init__  # type: ignore[misc]

    return provider_cls
