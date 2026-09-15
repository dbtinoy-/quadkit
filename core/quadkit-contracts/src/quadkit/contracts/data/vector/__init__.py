"""Vector store contracts — protocols, types, and filter primitives.

These define the interface boundary for all vector store backends.
Application code depends on these protocols. Concrete implementations
live in ``quadkit-vector``.

Basic Usage:
    ```python
    from quadkit.contracts.data.vector import (
        VectorStoreProtocol,
        VectorCollectionProtocol,
        VectorRecord,
        SearchQuery,
        Filter,
    )
    ```
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.data.vector.enums import (
        DistanceMetric,
        IndexState,
        IndexType,
    )
    from quadkit.contracts.data.vector.exceptions import (
        EmbeddingError,
        VectorError,
        VectorIndexError,
        VectorStoreError,
    )
    from quadkit.contracts.data.vector.filters import (
        Filter,
        FilterOperator,
        LogicalOperator,
        MetadataCondition,
        MetadataConditionGroup,
        MetadataFilter,
    )
    from quadkit.contracts.data.vector.protocols import (
        VectorCollectionProtocol,
        VectorStoreProtocol,
    )
    from quadkit.contracts.data.vector.tenancy import (
        TenantCollectionResolver,
    )
    from quadkit.contracts.data.vector.types import (
        CollectionConfig,
        CollectionInfo,
        DeleteResult,
        SearchQuery,
        UpsertResult,
        VectorRecord,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    # --- Exceptions ---
    "VectorError": (
        "quadkit.contracts.data.vector.exceptions",
        "VectorError",
    ),
    "VectorStoreError": (
        "quadkit.contracts.data.vector.exceptions",
        "VectorStoreError",
    ),
    "EmbeddingError": (
        "quadkit.contracts.data.vector.exceptions",
        "EmbeddingError",
    ),
    "VectorIndexError": (
        "quadkit.contracts.data.vector.exceptions",
        "VectorIndexError",
    ),
    # --- Protocols ---
    "VectorStoreProtocol": (
        "quadkit.contracts.data.vector.protocols",
        "VectorStoreProtocol",
    ),
    "VectorCollectionProtocol": (
        "quadkit.contracts.data.vector.protocols",
        "VectorCollectionProtocol",
    ),
    # --- Types ---
    "VectorRecord": (
        "quadkit.contracts.data.vector.types",
        "VectorRecord",
    ),
    "SearchQuery": (
        "quadkit.contracts.data.vector.types",
        "SearchQuery",
    ),
    "SearchResult": (
        "quadkit.contracts.data.vector.types",
        "SearchResult",
    ),
    "CollectionConfig": (
        "quadkit.contracts.data.vector.types",
        "CollectionConfig",
    ),
    "CollectionInfo": (
        "quadkit.contracts.data.vector.types",
        "CollectionInfo",
    ),
    "UpsertResult": (
        "quadkit.contracts.data.vector.types",
        "UpsertResult",
    ),
    "DeleteResult": (
        "quadkit.contracts.data.vector.types",
        "DeleteResult",
    ),
    # --- Tenancy ---
    "TenantCollectionResolver": (
        "quadkit.contracts.data.vector.tenancy",
        "TenantCollectionResolver",
    ),
    # --- Enums ---
    "DistanceMetric": (
        "quadkit.contracts.data.vector.enums",
        "DistanceMetric",
    ),
    "IndexType": (
        "quadkit.contracts.data.vector.enums",
        "IndexType",
    ),
    "IndexState": (
        "quadkit.contracts.data.vector.enums",
        "IndexState",
    ),
    # --- Filters ---
    "Filter": (
        "quadkit.contracts.data.vector.filters",
        "Filter",
    ),
    "MetadataFilter": (
        "quadkit.contracts.data.vector.filters",
        "MetadataFilter",
    ),
    "MetadataCondition": (
        "quadkit.contracts.data.vector.filters",
        "MetadataCondition",
    ),
    "MetadataConditionGroup": (
        "quadkit.contracts.data.vector.filters",
        "MetadataConditionGroup",
    ),
    "FilterOperator": (
        "quadkit.contracts.data.vector.filters",
        "FilterOperator",
    ),
    "LogicalOperator": (
        "quadkit.contracts.data.vector.filters",
        "LogicalOperator",
    ),
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
    "CollectionConfig",
    "CollectionInfo",
    "DeleteResult",
    "DistanceMetric",
    "EmbeddingError",
    "Filter",
    "FilterOperator",
    "IndexState",
    "IndexType",
    "LogicalOperator",
    "MetadataCondition",
    "MetadataConditionGroup",
    "MetadataFilter",
    "SearchQuery",
    "SearchResult",
    "TenantCollectionResolver",
    "UpsertResult",
    "VectorCollectionProtocol",
    "VectorError",
    "VectorIndexError",
    "VectorRecord",
    "VectorStoreError",
    "VectorStoreProtocol",
]
