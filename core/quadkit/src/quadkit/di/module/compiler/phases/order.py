"""ProviderOrderingPhase — topological sort and boot-level assignment."""

from __future__ import annotations

from quadkit.di.module.compiler._graph_utils import (
    compute_module_boot_levels,
    topological_sort_modules,
)
from quadkit.di.module.compiler.context import CompilerContext
from quadkit.di.module.graph import ProviderEntry


class ProviderOrderingPhase:
    """Phase 6: Produce a flat, topologically ordered list of ProviderEntry objects.

    Ordering rules:

    1. Imported-module providers come before the importing module's providers
       (topological sort of the import graph).
    2. Within a module, providers follow their declaration order.
    3. Standalone providers (``ctx.standalone_providers``) are appended last,
       at the highest boot level + 1.

    Writes ``ctx.provider_order``.
    """

    def execute(self, ctx: CompilerContext) -> None:
        """Populate ``ctx.provider_order``.

        Args:
            ctx: Shared compilation state.  Reads ``nodes`` and
                ``standalone_providers``; writes ``provider_order``.
        """
        module_order = topological_sort_modules(ctx.nodes)
        boot_level_map = compute_module_boot_levels(ctx.nodes, module_order)

        entries: list[ProviderEntry] = []

        for module_class in module_order:
            node = ctx.nodes[module_class]
            level = boot_level_map.get(module_class, 0)

            for provider in node.providers:
                is_instance = not isinstance(provider, type)
                entries.append(
                    ProviderEntry(
                        provider=provider,
                        module_class=module_class,
                        module_name=node.name,
                        boot_level=level,
                        is_instance=is_instance,
                    ),
                )

        if ctx.standalone_providers:
            max_level = max((e.boot_level for e in entries), default=-1) + 1
            for provider in ctx.standalone_providers:
                entries.append(
                    ProviderEntry(
                        provider=provider,
                        module_class=None,
                        module_name=None,
                        boot_level=max_level,
                        is_instance=True,
                    ),
                )

        ctx.provider_order = entries
