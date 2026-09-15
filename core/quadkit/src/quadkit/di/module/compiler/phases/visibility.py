"""VisibilityPhase — compute per-module visibility sets and global exports."""

from __future__ import annotations

from quadkit.di.module.compiler.context import CompilerContext


class VisibilityPhase:
    """Phase 5: Compute the type-visibility set for every module.

    A module can see:

    - All types in its own ``exports`` (proxy for its own providers'
      declared types; true validation happens post-registration).
    - All exports from every directly imported module.
    - All exports from every global module in the graph.

    Writes ``ctx.visibility`` and ``ctx.global_exports``.
    """

    def execute(self, ctx: CompilerContext) -> None:
        """Populate ``ctx.visibility`` and ``ctx.global_exports``.

        Args:
            ctx: Shared compilation state.  Reads ``nodes``; writes
                ``visibility`` and ``global_exports``.
        """
        ctx.global_exports = self._compute_global_exports(ctx)
        ctx.visibility = self._compute_visibility(ctx)

    def _compute_global_exports(self, ctx: CompilerContext) -> frozenset[type]:
        """Compute the union of all global-module exports.

        Args:
            ctx: Shared compilation state.

        Returns:
            Frozen set of types exported by every global module.
        """
        global_types: set[type] = set()
        for node in ctx.nodes.values():
            if node.is_global:
                global_types.update(node.exports)
        return frozenset(global_types)

    def _compute_visibility(
        self,
        ctx: CompilerContext,
    ) -> dict[type, frozenset[type]]:
        """Compute the visibility set for each module.

        Args:
            ctx: Shared compilation state.  ``ctx.global_exports`` must
                already be set before calling this method.

        Returns:
            Mapping of module class → frozenset of visible types.
        """
        visibility: dict[type, frozenset[type]] = {}

        for cls, node in ctx.nodes.items():
            visible: set[type] = set()

            visible.update(node.exports)

            for imp_cls in node.imports:
                imp_node = ctx.nodes.get(imp_cls)
                if imp_node:
                    visible.update(imp_node.exports)

            visible.update(ctx.global_exports)

            visibility[cls] = frozenset(visible)

        return visibility
