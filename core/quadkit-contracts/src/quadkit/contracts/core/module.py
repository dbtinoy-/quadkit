"""Module protocol definitions for the Quadkit framework.

These protocols define the structural contracts for modules at the
contract layer.  External packages (``quadkit-web``, ``quadkit-sql``,
etc.) can type-hint against these protocols without importing
``quadkit`` core.

The concrete implementations (``Module``, ``DynamicModule``,
``ModuleMetadata``, ``ModuleCompiler``) live in
``quadkit.di.module`` within the core package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence


@runtime_checkable
class ModuleMetadataProtocol(Protocol):
    """Structural protocol for module metadata descriptors.

    Satisfied by :class:`quadkit.di.module.ModuleMetadata`.
    """

    @property
    def name(self) -> str: ...

    @property
    def providers(self) -> tuple[type, ...]: ...

    @property
    def imports(self) -> tuple[type | Any, ...]: ...

    @property
    def exports(self) -> tuple[type, ...]: ...

    @property
    def controllers(self) -> tuple[type, ...]: ...

    @property
    def is_global(self) -> bool: ...


@runtime_checkable
class ModuleProtocol(Protocol):
    """Structural protocol for module classes.

    A class satisfies this protocol if it has a ``__quadkit_module__``
    attribute containing module metadata.  This is automatically
    attached by the ``@module()`` decorator.

    Usage in type hints::

        def process_module(mod: ModuleProtocol) -> None:
            meta = mod.__quadkit_module__
            print(f"Module {meta.name} has {len(meta.providers)} providers")
    """

    @property
    def __quadkit_module__(self) -> ModuleMetadataProtocol: ...


@runtime_checkable
class DynamicModuleProtocol(Protocol):
    """Structural protocol for dynamic module descriptors.

    Satisfied by :class:`quadkit.di.module.DynamicModule`.
    Dynamic modules are returned by factory methods like
    ``Module.configure()`` and fully replace the static ``@module()``
    metadata for the referenced module class.
    """

    @property
    def module(self) -> type:
        """The module class this descriptor configures (identity key)."""
        ...

    @property
    def providers(self) -> list[type | Any]:
        """Provider classes or pre-constructed instances."""
        ...

    @property
    def imports(self) -> list[type | Any]:
        """Module classes or nested dynamic module descriptors."""
        ...

    @property
    def exports(self) -> list[type]:
        """Contract types visible to importing modules."""
        ...

    @property
    def controllers(self) -> list[type]:
        """Controller classes for this module."""
        ...

    @property
    def is_global(self) -> bool:
        """Whether exports are universally visible."""
        ...

    @property
    def resolved_name(self) -> str:
        """Module name (explicit or derived from module class)."""
        ...


@runtime_checkable
class CompiledModuleGraphProtocol(Protocol):
    """Structural protocol for the compiled module graph.

    Satisfied by :class:`quadkit.di.module.CompiledModuleGraph`.
    """

    @property
    def provider_order(self) -> Sequence[Any]:
        """Providers in registration order."""
        ...

    @property
    def global_exports(self) -> frozenset[type]:
        """Union of all global module exports."""
        ...

    @property
    def warnings(self) -> list[str]:
        """Non-fatal issues detected during compilation."""
        ...

    def is_visible(self, from_module: type, service_type: type) -> bool:
        """Check if a service type is visible to a module."""
        ...

    def get_module_names(self) -> list[str]:
        """Return all module names in the graph."""
        ...


@runtime_checkable
class ModuleCompilerProtocol(Protocol):
    """Protocol for the module graph compiler.

    Satisfied by :class:`quadkit.di.module.ModuleCompiler`.
    """

    def compile(
        self,
        root_modules: list[type | Any],
        standalone_providers: list[Any] | None = None,
    ) -> CompiledModuleGraphProtocol:
        """Compile the module graph.

        Args:
            root_modules: Module classes and/or dynamic module instances.
            standalone_providers: Provider instances not belonging to
                any module.

        Returns:
            A compiled module graph ready for the orchestrator.
        """
        ...


@runtime_checkable
class ModuleRegistryProtocol(Protocol):
    """Protocol for runtime module ownership tracking.

    Satisfied by :class:`quadkit.di.module.ModuleRegistry`.
    """

    def register_ownership(
        self,
        service_type: type,
        module_class: type | None,
        provider_name: str | None = None,
    ) -> None:
        """Record that a service type was registered by a module."""
        ...

    def get_owner(self, service_type: type) -> type | None:
        """Get the module that owns a service type."""
        ...

    def get_module_services(self, module_class: type) -> frozenset[type]:
        """Get all service types registered by a module."""
        ...

    def validate_exports(
        self,
        graph: CompiledModuleGraphProtocol,
        container: Any | None = None,
    ) -> list[str]:
        """Validate that declared exports were actually registered."""
        ...


__all__ = [
    "CompiledModuleGraphProtocol",
    "DynamicModuleProtocol",
    "ModuleCompilerProtocol",
    "ModuleMetadataProtocol",
    "ModuleProtocol",
    "ModuleRegistryProtocol",
]
