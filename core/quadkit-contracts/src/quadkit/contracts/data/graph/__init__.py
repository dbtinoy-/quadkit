"""Graph store contracts — protocols, types, and filter primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.data.graph.enums import (
        ConstraintKind,
        EdgeDirection,
        IndexKind,
        MergeAction,
        ReturnType,
    )
    from quadkit.contracts.data.graph.filters import (
        Prop,
        PropertyCondition,
        PropertyConditionGroup,
        PropertyFilter,
        PropertyOperator,
    )
    from quadkit.contracts.data.graph.protocols import (
        GraphProtocol,
        GraphStoreProtocol,
    )
    from quadkit.contracts.data.graph.tenancy import (
        GraphTenancyStrategy,
    )
    from quadkit.contracts.data.graph.types import (
        BulkEdgeResult,
        BulkNodeResult,
        ConstraintSpec,
        EdgeResult,
        EdgeSpec,
        GraphEdge,
        GraphInfo,
        GraphNode,
        GraphPath,
        IndexSpec,
        NodeResult,
        NodeSpec,
        StartSpec,
        TraversalQuery,
        TraversalStep,
    )
    from quadkit.contracts.data.types import LogicalOperator

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # --- Protocols ---
    "GraphStoreProtocol": (
        "quadkit.contracts.data.graph.protocols",
        "GraphStoreProtocol",
    ),
    "GraphProtocol": (
        "quadkit.contracts.data.graph.protocols",
        "GraphProtocol",
    ),
    # --- Types ---
    "GraphNode": ("quadkit.contracts.data.graph.types", "GraphNode"),
    "GraphEdge": ("quadkit.contracts.data.graph.types", "GraphEdge"),
    "GraphPath": ("quadkit.contracts.data.graph.types", "GraphPath"),
    "NodeSpec": ("quadkit.contracts.data.graph.types", "NodeSpec"),
    "EdgeSpec": ("quadkit.contracts.data.graph.types", "EdgeSpec"),
    "NodeResult": ("quadkit.contracts.data.graph.types", "NodeResult"),
    "EdgeResult": ("quadkit.contracts.data.graph.types", "EdgeResult"),
    "BulkNodeResult": ("quadkit.contracts.data.graph.types", "BulkNodeResult"),
    "BulkEdgeResult": ("quadkit.contracts.data.graph.types", "BulkEdgeResult"),
    "GraphInfo": ("quadkit.contracts.data.graph.types", "GraphInfo"),
    "StartSpec": ("quadkit.contracts.data.graph.types", "StartSpec"),
    "TraversalStep": ("quadkit.contracts.data.graph.types", "TraversalStep"),
    "TraversalQuery": ("quadkit.contracts.data.graph.types", "TraversalQuery"),
    "IndexSpec": ("quadkit.contracts.data.graph.types", "IndexSpec"),
    "ConstraintSpec": ("quadkit.contracts.data.graph.types", "ConstraintSpec"),
    # --- Enums ---
    "EdgeDirection": ("quadkit.contracts.data.graph.enums", "EdgeDirection"),
    "ReturnType": ("quadkit.contracts.data.graph.enums", "ReturnType"),
    "IndexKind": ("quadkit.contracts.data.graph.enums", "IndexKind"),
    "ConstraintKind": ("quadkit.contracts.data.graph.enums", "ConstraintKind"),
    "MergeAction": ("quadkit.contracts.data.graph.enums", "MergeAction"),
    # --- Tenancy ---
    "GraphTenancyStrategy": (
        "quadkit.contracts.data.graph.tenancy",
        "GraphTenancyStrategy",
    ),
    # --- Filters ---
    "Prop": ("quadkit.contracts.data.graph.filters", "Prop"),
    "PropertyFilter": ("quadkit.contracts.data.graph.filters", "PropertyFilter"),
    "PropertyCondition": ("quadkit.contracts.data.graph.filters", "PropertyCondition"),
    "PropertyConditionGroup": (
        "quadkit.contracts.data.graph.filters",
        "PropertyConditionGroup",
    ),
    "PropertyOperator": ("quadkit.contracts.data.graph.filters", "PropertyOperator"),
    "LogicalOperator": ("quadkit.contracts.data.types", "LogicalOperator"),
}


def __getattr__(name: str) -> Any:
    """Lazy-load symbols on first access."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Enumerate available attributes for IDE support."""
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "BulkEdgeResult",
    "BulkNodeResult",
    "ConstraintKind",
    "ConstraintSpec",
    "EdgeDirection",
    "EdgeResult",
    "EdgeSpec",
    "GraphEdge",
    "GraphInfo",
    "GraphNode",
    "GraphPath",
    "GraphProtocol",
    "GraphStoreProtocol",
    "GraphTenancyStrategy",
    "IndexKind",
    "IndexSpec",
    "LogicalOperator",
    "MergeAction",
    "NodeResult",
    "NodeSpec",
    "Prop",
    "PropertyCondition",
    "PropertyConditionGroup",
    "PropertyFilter",
    "PropertyOperator",
    "ReturnType",
    "StartSpec",
    "TraversalQuery",
    "TraversalStep",
]
