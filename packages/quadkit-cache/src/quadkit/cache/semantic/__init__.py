"""Semantic cache for LLM response caching with vector similarity search.

Provides three-tier semantic caching: exact hash matching, vector similarity
matching, and cache miss fallback. Supports optional cost-aware cache
hit decision logic.

Exports:
    SemanticCacheStore: Three-tier semantic cache implementation.
    FaissVectorIndex: FAISS-backed in-memory vector index.
    CostAwareCacheDecision: Cost-aware cache hit decision function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.cache.semantic.cost_decision import CostAwareCacheDecision
    from quadkit.cache.semantic.store import SemanticCacheStore
    from quadkit.cache.semantic.vector_index import FaissVectorIndex

_LAZY_IMPORTS = {
    "CostAwareCacheDecision": "quadkit.cache.semantic.cost_decision",
    "FaissVectorIndex": "quadkit.cache.semantic.vector_index",
    "SemanticCacheStore": "quadkit.cache.semantic.store",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module_path = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> Any:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = list(_LAZY_IMPORTS.keys())
