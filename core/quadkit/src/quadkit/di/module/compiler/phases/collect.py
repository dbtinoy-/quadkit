"""CollectPhase — walk the import tree and build the module node map."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.constants import DOCS_BASE_URL
from quadkit.contracts.exceptions.provider import ModuleDuplicateError, ModuleError
from quadkit.di.module.compiler.context import CompilerContext
from quadkit.di.module.errors import (
    format_duplicate_module_error,
    format_not_a_module_error,
)
from quadkit.di.module.graph import ModuleNode
from quadkit.di.module.introspection import get_module_metadata, is_dynamic_module
from quadkit.di.module.metadata import ModuleMetadata
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.module.dynamic import DynamicModule

logger = get_logger(__name__)


class CollectPhase:
    """Phase 1: Collect all reachable modules from the root list.

    Walks the import tree recursively from each entry in
    ``ctx.root_modules``, creating a :class:`ModuleNode` for every
    unique module class encountered.  Duplicate module classes with
    conflicting :class:`DynamicModule` configurations raise
    :exc:`ModuleDuplicateError`.
    """

    def execute(self, ctx: CompilerContext) -> None:
        """Populate ``ctx.nodes`` and ``ctx.dynamic_configs``.

        Args:
            ctx: Shared compilation state.  Reads ``root_modules``; writes
                ``nodes`` and ``dynamic_configs``.
        """
        for entry in ctx.root_modules:
            self._collect(entry, ctx)

        logger.debug(
            "compiler.collected",
            module_count=len(ctx.nodes),
            modules=[n.name for n in ctx.nodes.values()],
        )

    def _collect(self, entry: type | DynamicModule, ctx: CompilerContext) -> type:
        """Recursively collect a module and all its imports.

        Args:
            entry: A module class or :class:`DynamicModule` instance.
            ctx: The compilation context to mutate.

        Returns:
            The module class used as the identity key.

        Raises:
            ModuleDuplicateError: Same module class with conflicting configs.
            ModuleError: Entry is not a valid module.
        """
        if is_dynamic_module(entry):
            dynamic: DynamicModule = entry  # type: ignore[assignment]
            module_class = dynamic.module
            return self._collect_dynamic(module_class, dynamic, ctx)
        if isinstance(entry, type):
            return self._collect_static(entry, ctx)
        name = getattr(entry, "__name__", repr(entry))
        raise ModuleError(
            format_not_a_module_error(name, type(entry).__name__),
            hint="Pass an @module()-decorated class or a DynamicModule from configure().",
        )

    def _collect_static(self, cls: type, ctx: CompilerContext) -> type:
        """Collect a statically-decorated module class.

        Args:
            cls: A class decorated with ``@module``.
            ctx: The compilation context to mutate.

        Returns:
            The module class.

        Raises:
            ModuleError: If the class is not decorated with ``@module``.
        """
        if cls in ctx.nodes:
            return cls

        meta = get_module_metadata(cls)
        if meta is None:
            raise ModuleError(
                f"'{cls.__name__}' is not decorated with @module.\n"
                f"\n"
                f"Reference: {DOCS_BASE_URL}/fundamentals/modules/",
                hint=(
                    f"Add @module() to {cls.__name__}, or import "
                    f"{cls.__name__}.configure() instead."
                ),
            )

        # DynamicModule was collected first — it takes precedence
        if cls in ctx.dynamic_configs:
            return cls

        node = ModuleNode(
            module_class=cls,
            name=meta.name,
            metadata=meta,
            providers=list(meta.providers),
            imports=[self._resolve_import_class(imp) for imp in meta.imports],
            exports=frozenset(meta.exports),
            is_global=meta.is_global,
            is_dynamic=False,
            controllers=list(meta.controllers),
            health_providers=None,
        )
        ctx.nodes[cls] = node

        for imp in meta.imports:
            self._collect(imp, ctx)

        return cls

    def _collect_dynamic(
        self,
        module_class: type,
        dynamic: DynamicModule,
        ctx: CompilerContext,
    ) -> type:
        """Collect a DynamicModule-configured module.

        Args:
            module_class: The backing class for this dynamic module.
            dynamic: The :class:`DynamicModule` descriptor.
            ctx: The compilation context to mutate.

        Returns:
            The module class.

        Raises:
            ModuleDuplicateError: If the same class has a conflicting config.
        """
        if module_class in ctx.dynamic_configs:
            existing = ctx.dynamic_configs[module_class]
            if existing is not dynamic:
                raise ModuleDuplicateError(
                    format_duplicate_module_error(
                        module_class.__name__,
                        repr(existing),
                        repr(dynamic),
                    ),
                    module_name=module_class.__name__,
                    hint=(
                        f"Keep a single configure() call for {module_class.__name__} "
                        "in the application module graph."
                    ),
                )
            return module_class

        ctx.dynamic_configs[module_class] = dynamic

        # Inherit is_global from the class-level @module() decorator when the
        # DynamicModule doesn't explicitly enable it.  This ensures that modules
        # decorated with @module(is_global=True) remain globally visible even
        # when configure() omits the is_global flag.
        class_meta = get_module_metadata(module_class)
        effective_is_global = dynamic.is_global or (
            class_meta is not None and class_meta.is_global
        )

        provider_types: tuple[Any, ...] = tuple(
            p if isinstance(p, type) else type(p) for p in dynamic.providers
        )
        meta = ModuleMetadata(
            name=dynamic.resolved_name,
            providers=list(provider_types),
            imports=[self._resolve_import_class(imp) for imp in dynamic.imports],
            exports=list(dynamic.exports),
            controllers=list(dynamic.controllers),
            is_global=effective_is_global,
        )

        node = ModuleNode(
            module_class=module_class,
            name=dynamic.resolved_name,
            metadata=meta,
            providers=list(dynamic.providers),
            imports=[self._resolve_import_class(imp) for imp in dynamic.imports],
            exports=frozenset(dynamic.exports),
            is_global=effective_is_global,
            is_dynamic=True,
            controllers=list(dynamic.controllers),
            health_providers=dynamic.health_providers,
        )

        ctx.nodes[module_class] = node

        for imp in dynamic.imports:
            self._collect(imp, ctx)

        return module_class

    def _resolve_import_class(self, entry: type | DynamicModule) -> type:
        """Extract the module class from an import entry.

        Args:
            entry: A module class or :class:`DynamicModule` instance.

        Returns:
            The module class.
        """
        if is_dynamic_module(entry):
            return entry.module  # type: ignore[union-attr]
        return entry  # type: ignore[return-value]
