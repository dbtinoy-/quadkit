"""DynamicModule — runtime-configured module descriptor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.exceptions.provider import ModuleError


def _describe_dynamic_entry(entry: Any) -> str:
    """Return a concise label for DynamicModule repr output."""
    if isinstance(entry, type):
        return entry.__name__
    return type(entry).__name__


@dataclass
class DynamicModule:
    """Runtime-configured module descriptor.

    Returned by factory methods like ``Module.configure()`` and
    ``Module.scope()``.  When a ``DynamicModule`` appears in an
    import list or is passed to ``Application.add_module()``, it **fully
    replaces** the static ``@module()`` metadata for the referenced
    module class.

    Provider entries may be **classes** (instantiated by the orchestrator)
    or **pre-constructed instances** (registered directly)::

        DynamicModule(
            module=CacheModule,
            providers=[
                CacheProvider(backend="redis"),   # instance
                MetricsProvider,                  # class
            ],
            exports=[CacheBackendProtocol],
            is_global=True,
        )

    Identity and Deduplication:
        The :attr:`module` field determines identity.  Two
        ``DynamicModule`` entries referencing the same module class but
        with different configurations raise ``ModuleDuplicateError``
        at compile time.
    """

    module: type
    """The module class this descriptor configures (identity key)."""

    providers: list[type | Any] = field(default_factory=list)
    """Provider classes or pre-constructed provider instances."""

    imports: list[type | DynamicModule] = field(default_factory=list)
    """Module classes or nested ``DynamicModule`` descriptors."""

    exports: list[type] = field(default_factory=list)
    """Contract/protocol types visible to importing modules."""

    controllers: list[type] = field(default_factory=list)
    """Controller classes for this module."""

    is_global: bool = False
    """If ``True``, exports are visible to ALL modules without import."""

    name: str | None = None
    """Override the module name (defaults to ``module.__name__``)."""

    health_providers: list[type | str] | None = None
    """Service types or paths to use for health checks (optional)."""

    def __post_init__(self) -> None:
        if not isinstance(self.module, type):
            raise ModuleError(
                f"DynamicModule.module must be a class, got "
                f"{type(self.module).__name__}: {self.module!r}",
            )

    @property
    def resolved_name(self) -> str:
        """Module name: explicit :attr:`name` or ``module.__name__``."""
        return self.name or self.module.__name__

    def __repr__(self) -> str:
        parts = [f"<DynamicModule {self.resolved_name!r}"]
        if self.providers:
            providers = ", ".join(
                _describe_dynamic_entry(provider) for provider in self.providers
            )
            parts.append(f" providers=[{providers}]")
        if self.imports:
            imports = ", ".join(
                entry.resolved_name
                if isinstance(entry, DynamicModule)
                else entry.__name__
                for entry in self.imports
            )
            parts.append(f" imports=[{imports}]")
        if self.exports:
            exports = ", ".join(export.__name__ for export in self.exports)
            parts.append(f" exports=[{exports}]")
        if self.is_global:
            parts.append(" is_global=True")
        parts.append(">")
        return "".join(parts)
