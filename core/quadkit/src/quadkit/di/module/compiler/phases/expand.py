"""ReexportExpansionPhase — expand module-class re-exports to concrete types."""

from __future__ import annotations

from quadkit.di.module.compiler._graph_utils import topological_sort_modules
from quadkit.di.module.compiler.context import CompilerContext
from quadkit.di.module.graph import ModuleNode
from quadkit.logging import get_logger

logger = get_logger(__name__)


class ReexportExpansionPhase:
    """Phase 4: Expand module-class entries in export lists to concrete types.

    When a module lists another module class in its ``exports``, all
    exports of that imported module become exports of the declaring module.
    Processing is done in topological order so that re-exports of
    re-exports are resolved correctly.

    Modifies ``ctx.nodes`` in place by replacing the ``exports`` frozenset
    on affected nodes.
    """

    def execute(self, ctx: CompilerContext) -> None:
        """Expand all module-class re-exports in ``ctx.nodes``.

        Args:
            ctx: Shared compilation state.  Reads and writes ``nodes``.
        """
        module_order = topological_sort_modules(ctx.nodes)
        for cls in module_order:
            node = ctx.nodes[cls]
            expanded: set[type] = set()
            for export_type in node.exports:
                if export_type in ctx.nodes:
                    reexported_node = ctx.nodes[export_type]
                    expanded.update(reexported_node.exports)
                    logger.debug(
                        "compiler.reexport_expanded",
                        module=node.name,
                        reexported_module=reexported_node.name,
                        types=len(reexported_node.exports),
                    )
                else:
                    expanded.add(export_type)

            if expanded != node.exports:
                ctx.nodes[cls] = ModuleNode(
                    module_class=node.module_class,
                    name=node.name,
                    metadata=node.metadata,
                    providers=node.providers,
                    imports=node.imports,
                    exports=frozenset(expanded),
                    is_global=node.is_global,
                    is_dynamic=node.is_dynamic,
                    controllers=node.controllers,
                    health_providers=node.health_providers,
                )
