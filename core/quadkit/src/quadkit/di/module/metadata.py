"""ModuleMetadata — module descriptor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.exceptions.provider import ModuleError


@dataclass
class ModuleMetadata:
    """Descriptor of a module's structural declarations.

    Attached to module classes by the :func:`module` decorator via the
    ``__quadkit_module__`` attribute.  Contains **structural data** plus
    the :meth:`configure_builder` helper used by cycle detection tests.

    Validation, compilation, and lifecycle management are the primary
    responsibility of the ``ModuleCompiler`` and ``ProviderOrchestrator``.

    .. note::

        This type will migrate to ``quadkit.contracts.core.module``
        once the module system stabilises, allowing external packages
        to reference module metadata without importing core.
    """

    name: str

    providers: list[type | Any] = field(default_factory=list)
    """Provider classes or pre-constructed provider instances."""

    imports: list[type | Any] = field(default_factory=list)
    """Module classes or :class:`DynamicModule` descriptors this module depends on."""

    exports: list[type] = field(default_factory=list)
    """Contract types visible to importing modules.

    A **module class** in this list is a re-export: importers
    transitively receive all of that module's exports.
    """

    controllers: list[type] = field(default_factory=list)
    """Controller classes registered with the web layer."""

    is_global: bool = False
    """If ``True``, exports are visible to all modules without explicit import."""

    require_stub: bool = False
    """If ``True``, this module requires a stub (test double) in test environments.

    When set, the ``ModuleCompiler`` will warn or error if this module is
    used in a test context without a corresponding stub registered.
    """

    scan: list[str] = field(default_factory=list)
    """Package paths to scan for ``@injectable`` / ``@singleton`` classes.

    When set, the module decorator discovers annotated classes in these
    packages and auto-generates a synthetic provider that registers them
    into the DI container during boot.
    """

    __quadkit_owner__: type | None = field(default=None, init=False, repr=False)
    """The module class that owns this metadata (set by the decorator)."""

    def __post_init__(self) -> None:
        """Validate structural constraints at creation time."""
        _validate_metadata(self)

    def __repr__(self) -> str:
        from quadkit.di.module.dynamic import DynamicModule

        parts = [f"name={self.name!r}"]
        if self.providers:
            names = ", ".join(p.__name__ for p in self.providers)
            parts.append(f"providers=[{names}]")
        if self.imports:
            import_names: list[str] = []
            for imp in self.imports:
                if isinstance(imp, DynamicModule):
                    import_names.append(f"{imp.resolved_name}(dynamic)")
                else:
                    import_names.append(imp.__name__)
            parts.append(f"imports=[{', '.join(import_names)}]")
        if self.exports:
            names = ", ".join(e.__name__ for e in self.exports)
            parts.append(f"exports=[{names}]")
        if self.controllers:
            names = ", ".join(c.__name__ for c in self.controllers)
            parts.append(f"controllers=[{names}]")
        if self.is_global:
            parts.append("is_global=True")
        if self.scan:
            parts.append(f"scan={self.scan!r}")
        return f"ModuleMetadata({', '.join(parts)})"

    def configure_builder(
        self,
        builder: Any,
        _visited: set[type] | None = None,
    ) -> None:
        """Recursively configure a builder with this module's providers.

        Performs DFS traversal of the import graph.  Raises
        :class:`~quadkit.contracts.exceptions.provider.ModuleCycleError`
        if a circular dependency is detected.

        Args:
            builder: An object with ``add_module(cls)`` and
                ``add_provider(instance)`` methods.
            _visited: Internal set used for cycle detection.  Pass
                ``None`` (the default) when calling from user code.

        Raises:
            ModuleCycleError: If a circular module dependency is detected.
        """
        from quadkit.contracts.exceptions.provider import ModuleCycleError
        from quadkit.di.module.dynamic import DynamicModule

        if _visited is None:
            _visited = set()

        owner = self.__quadkit_owner__
        if owner is not None:
            if owner in _visited:
                raise ModuleCycleError(
                    f"Circular module dependency detected involving '{self.name}'",
                )
            _visited.add(owner)
            builder.add_module(owner)

        # Depth-first: recurse into imports before registering own providers
        for imp in self.imports:
            if isinstance(imp, DynamicModule):
                for p in imp.providers:
                    builder.add_provider(p if not isinstance(p, type) else p())
            else:
                imp_meta = getattr(imp, "__quadkit_module__", None)
                if imp_meta is not None:
                    imp_meta.configure_builder(builder, _visited)

        for provider_cls in self.providers:
            if isinstance(provider_cls, type):
                builder.add_provider(provider_cls())
            else:
                builder.add_provider(provider_cls)


def _validate_metadata(meta: ModuleMetadata) -> None:
    """Validate structural constraints of :class:`ModuleMetadata`.

    Performs **shallow** type checks only.  Deep validation — cycle
    detection, missing imports, export coverage — is the
    ``ModuleCompiler``'s responsibility.

    Raises:
        ModuleError: If a provider, export, or controller entry has an
            invalid type.
        TypeError: If an imports entry is not a class or is a class that
            has not been decorated with ``@module``.
    """
    from quadkit.di.module.dynamic import DynamicModule

    for i, entry in enumerate(meta.providers):
        if not isinstance(entry, type):
            raise ModuleError(
                f"Module '{meta.name}': providers[{i}] is an instance of "
                f"{type(entry).__name__}, expected a class (type). "
                f"Pass the class itself, or use DynamicModule to provide "
                f"pre-constructed provider instances.",
            )

    for i, entry in enumerate(meta.imports):
        if isinstance(entry, DynamicModule):
            continue
        if not isinstance(entry, type):
            raise TypeError(
                f"Module '{meta.name}': imports[{i}] is not a class "
                f"(got {type(entry).__name__!r}). "
                f"Each import must be a class decorated with @module or a DynamicModule.",
            )

    for i, entry in enumerate(meta.exports):
        if not isinstance(entry, type):
            raise ModuleError(
                f"Module '{meta.name}': exports[{i}] is "
                f"{type(entry).__name__}, expected a type (contract, "
                f"protocol, or module class for re-export).",
            )

    for i, entry in enumerate(meta.controllers):
        if not isinstance(entry, type):
            raise ModuleError(
                f"Module '{meta.name}': controllers[{i}] is "
                f"{type(entry).__name__}, expected a class.",
            )
