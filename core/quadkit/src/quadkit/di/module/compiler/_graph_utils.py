"""Shared topological-sort utilities for compiler phases."""

from __future__ import annotations

from collections import deque

from quadkit.contracts.exceptions.provider import ModuleCycleError
from quadkit.di.module.graph import ModuleNode


def topological_sort_modules(nodes: dict[type, ModuleNode]) -> list[type]:
    """Sort module classes so that every import precedes its importing module.

    Uses Kahn's algorithm on the module import graph.

    Args:
        nodes: The full node map from :class:`CompilerContext`.

    Returns:
        Module classes in topological (imports-first) order.

    Raises:
        ModuleCycleError: If a cycle remains after :class:`CycleDetectionPhase`
            (safety net only — should not be reached in normal usage).
    """
    in_degree: dict[type, int] = dict.fromkeys(nodes, 0)
    dependents: dict[type, list[type]] = {cls: [] for cls in nodes}

    for cls, node in nodes.items():
        for imp_cls in node.imports:
            if imp_cls in nodes:
                in_degree[cls] += 1
                dependents[imp_cls].append(cls)

    queue: deque[type] = deque(
        sorted(
            (cls for cls, deg in in_degree.items() if deg == 0),
            key=lambda c: nodes[c].name,
        ),
    )

    result: list[type] = []
    while queue:
        cls = queue.popleft()
        result.append(cls)

        for dep_cls in sorted(
            dependents[cls],
            key=lambda c: nodes[c].name,
        ):
            in_degree[dep_cls] -= 1
            if in_degree[dep_cls] == 0:
                queue.append(dep_cls)

    if len(result) != len(nodes):
        missing = {nodes[c].name for c in nodes if c not in set(result)}
        raise ModuleCycleError(
            f"Cycle detected during module ordering. Unplaced modules: {missing}",
            cycle=sorted(missing),
        )

    return result


def compute_module_boot_levels(
    nodes: dict[type, ModuleNode],
    module_order: list[type],
) -> dict[type, int]:
    """Assign a boot level to each module for parallel-boot grouping.

    Modules at the same level have no mutual import dependencies and can
    boot concurrently.

    Args:
        nodes: The full node map from :class:`CompilerContext`.
        module_order: Topologically sorted module classes.

    Returns:
        Mapping of module class → boot level (0-based).
    """
    levels: dict[type, int] = {}

    for cls in module_order:
        node = nodes[cls]
        if not node.imports:
            levels[cls] = 0
        else:
            max_dep_level = max(
                (levels.get(imp, 0) for imp in node.imports if imp in levels),
                default=0,
            )
            levels[cls] = max_dep_level + 1

    return levels
