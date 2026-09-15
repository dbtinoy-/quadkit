"""CycleDetectionPhase — DFS-based cycle detection on the module import graph."""

from __future__ import annotations

from enum import Enum

from quadkit.contracts.exceptions.provider import ModuleCycleError
from quadkit.di.module.compiler.context import CompilerContext
from quadkit.di.module.errors import format_cycle_error


class _Color(str, Enum):
    """DFS node coloring for cycle detection."""

    WHITE = "white"  # Not visited
    GRAY = "gray"  # In current DFS path (visiting)
    BLACK = "black"  # Fully processed


class CycleDetectionPhase:
    """Phase 2: Detect circular imports using DFS with three-color marking.

    A GRAY node encountered during DFS indicates a back-edge — a cycle.
    The full cycle path is included in the raised error message.
    """

    def execute(self, ctx: CompilerContext) -> None:
        """Scan ``ctx.nodes`` for import cycles.

        Args:
            ctx: Shared compilation state.  Reads ``nodes`` only.

        Raises:
            ModuleCycleError: If any circular import is detected.
        """
        colors: dict[type, _Color] = dict.fromkeys(ctx.nodes, _Color.WHITE)
        path: list[type] = []

        def _dfs(cls: type) -> None:
            colors[cls] = _Color.GRAY
            path.append(cls)

            node = ctx.nodes[cls]
            for imp_cls in node.imports:
                if imp_cls not in colors:
                    # Import not in graph — caught by ValidationPhase
                    continue

                if colors[imp_cls] == _Color.GRAY:
                    cycle_start = path.index(imp_cls)
                    cycle_classes = [*path[cycle_start:], imp_cls]
                    cycle_names = [
                        ctx.nodes[c].name if c in ctx.nodes else c.__name__
                        for c in cycle_classes
                    ]
                    raise ModuleCycleError(
                        format_cycle_error(cycle_names),
                        cycle=cycle_names,
                        hint="Extract shared exports into a third module to break the cycle.",
                    )

                if colors[imp_cls] == _Color.WHITE:
                    _dfs(imp_cls)

            path.pop()
            colors[cls] = _Color.BLACK

        for cls in ctx.nodes:
            if colors[cls] == _Color.WHITE:
                _dfs(cls)
