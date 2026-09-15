"""Module base class — optional convenience for factory patterns."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

if TYPE_CHECKING:
    from quadkit.di.module.dynamic import DynamicModule

_T = TypeVar("_T")


def _describe_module_entry(entry: Any) -> str:
    """Return a concise developer-facing name for module metadata entries."""
    from quadkit.di.module.dynamic import DynamicModule

    if isinstance(entry, DynamicModule):
        return entry.resolved_name
    if isinstance(entry, type):
        return entry.__name__
    return type(entry).__name__


def _describe_module_list(entries: list[Any]) -> str:
    """Render module metadata entry names for repr output."""
    return f"[{', '.join(_describe_module_entry(entry) for entry in entries)}]"


class ModuleMeta(type):
    """Metaclass that gives module classes a useful debug representation."""

    def __repr__(cls) -> str:
        metadata = getattr(cls, "__quadkit_module__", None)
        module_name = (
            getattr(metadata, "name", None)
            or getattr(cls, "name", None)
            or cls.__name__
        )

        parts = [f"<Module {module_name!r}"]
        providers = list(
            getattr(metadata, "providers", getattr(cls, "providers", [])) or []
        )
        imports = list(getattr(metadata, "imports", getattr(cls, "imports", [])) or [])
        exports = list(getattr(metadata, "exports", getattr(cls, "exports", [])) or [])

        if providers:
            parts.append(f" providers={_describe_module_list(providers)}")
        if exports:
            parts.append(f" exports={_describe_module_list(exports)}")
        if imports:
            parts.append(f" imports={_describe_module_list(imports)}")
        if getattr(metadata, "is_global", getattr(cls, "is_global", False)):
            parts.append(" is_global=True")
        parts.append(">")
        return "".join(parts)


class Module(metaclass=ModuleMeta):
    """Optional base class for module classes.

    Provides ``ClassVar`` defaults that the :func:`module` decorator
    reads, IDE autocompletion, and the ``configure()`` / ``scope()`` / ``stub()``
    factory pattern for creating :class:`DynamicModule` descriptors.

    **Inheriting from Module is NOT required** — any class decorated with
    ``@module()`` is a valid Quadkit module.  This base class is a
    convenience, not a mandate.

    ``Module`` instances can also be used directly as class decorators, which
    enables the root-module composition style familiar from other frameworks:

    .. code-block:: python

        @Module(imports=[UserModule, ProductModule])
        class AppModule(ModuleBase):
            pass

    ClassVar Inheritance::

        class BaseInfra(Module):
            providers = [LoggingProvider]

        @module()
        class FullInfra(BaseInfra):
            exports = [LoggerProtocol]

    Factory Pattern::

        @module()
        class DatabaseModule(Module):

            @classmethod
            def configure(cls, url: str) -> DynamicModule:
                return DynamicModule(
                    module=cls,
                    providers=[DatabaseProvider(url=url)],
                    exports=[DatabaseSession, TransactionManager],
                    is_global=True,
                )

            @classmethod
            def scope(cls, *models: type) -> DynamicModule:
                return DynamicModule(
                    module=cls,
                    providers=[ModelRegistryProvider(models)],
                )
    """

    name: ClassVar[str | None] = None
    providers: ClassVar[list[type]] = []
    imports: ClassVar[list[type]] = []
    exports: ClassVar[list[type]] = []
    controllers: ClassVar[list[type]] = []
    is_global: ClassVar[bool] = False
    scan: ClassVar[list[str]] = []

    def __init__(
        self,
        name: str | None = None,
        providers: list[type] | None = None,
        imports: list[Any] | None = None,
        exports: list[type] | None = None,
        controllers: list[type] | None = None,
        is_global: bool = False,
        scan: list[str] | None = None,
    ) -> None:
        """Optionally override ClassVar defaults with instance values.

        Args:
            name: Module name.
            providers: Provider classes declared by this module.
            imports: Module classes or DynamicModule instances to import.
            exports: Contract types to expose to importing modules.
            controllers: Controller classes registered with the web layer.
            is_global: When ``True``, exports are visible to all modules.
            scan: Package paths to scan for ``@injectable`` / ``@singleton`` classes.
        """
        if name is not None:
            self.name = name  # type: ignore[misc]
        if providers is not None:
            self.providers = providers  # type: ignore[misc]
        if imports is not None:
            self.imports = imports  # type: ignore[misc]
        if exports is not None:
            self.exports = exports  # type: ignore[misc]
        if controllers is not None:
            self.controllers = controllers  # type: ignore[misc]
        if is_global:
            self.is_global = is_global  # type: ignore[misc]
        if scan is not None:
            self.scan = scan  # type: ignore[misc]

    def __call__(self, cls: type[_T]) -> type[_T]:
        """Apply this Module instance as a class decorator.

        Attaches :class:`~quadkit.di.module.ModuleMetadata` to *cls* using
        the configuration held by this instance.  ClassVar defaults on *cls*
        are merged in the same way as when using the :func:`module` decorator
        directly — instance parameters override class-level defaults.

        Example::

            @Module(imports=[UserModule])
            class AppModule(ModuleBase):
                pass
        """
        from quadkit.di.module.decorator import _attach_metadata

        return _attach_metadata(
            cls,
            name=self.name if self.name is not None else None,
            providers=list(self.providers) if self.providers else None,
            imports=list(self.imports) if self.imports else None,
            exports=list(self.exports) if self.exports else None,
            controllers=list(self.controllers) if self.controllers else None,
            is_global=self.is_global,
            scan=list(self.scan) if self.scan else None,
        )

    def __repr__(self) -> str:
        return repr(self.__class__)

    @classmethod
    def configure(cls, *args: Any, **kwargs: Any) -> DynamicModule:
        """Configure this module globally. Called once at the app root.

        Args:
            *args: Positional arguments forwarded to the concrete implementation.
            **kwargs: Keyword arguments forwarded to the concrete implementation.

        Returns:
            DynamicModule for root import.

        Raises:
            NotImplementedError: Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{cls.__name__}.configure() is not implemented. "
            "Override configure() in your module subclass."
        )

    @classmethod
    def scope(cls, *providers: type, **kwargs: Any) -> DynamicModule:
        """Register additional providers in a per-feature scope.

        Creates an anonymous sub-class token so the compiler treats this
        as a distinct module (avoids ModuleDuplicateError when both
        configure() and scope() are imported into the same compiled graph).

        Args:
            *providers: Provider classes to register in this scope.
            **kwargs: Additional DynamicModule fields (imports, exports, etc.).

        Returns:
            DynamicModule with a unique anonymous token as module identity.
        """
        from quadkit.di.module.dynamic import DynamicModule

        token = type(
            f"_{cls.__name__}Scope",
            (cls,),
            {"__quadkit_scope_of__": cls},
        )
        return DynamicModule(
            module=token,
            providers=list(providers),
            exports=list(kwargs.get("exports", [])),
            imports=list(kwargs.get("imports", [])),
            is_global=False,
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return a test-mode module with in-memory/noop backends.

        Args:
            config: Optional test configuration override.

        Returns:
            DynamicModule using test providers.

        Raises:
            NotImplementedError: Subclasses must override this method.
        """
        raise NotImplementedError(
            f"{cls.__name__}.stub() is not implemented. "
            "Add a stub() classmethod that returns a DynamicModule using "
            "in-memory or noop test providers."
        )

    @classmethod
    async def on_module_booted(cls) -> None:
        """Called after all providers in this module have been booted.

        Override in subclasses to run post-boot initialization logic.
        The container is fully available at this point.
        """

    @classmethod
    async def on_module_shutdown(cls) -> None:
        """Called before this module's providers are shut down.

        Override in subclasses to run pre-shutdown cleanup logic.
        """


#: Alias for :class:`Module` — use as the base class when you prefer the
#: ``ModuleBase`` naming style from other frameworks.
ModuleBase = Module
