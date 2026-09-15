"""Search type aliases and value types.

Canonical definitions for search domain operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Type aliases
DocumentData = dict[str, Any]
IndexSettings = dict[str, Any]
SearchFilters = dict[str, Any]


@dataclass(frozen=True, slots=True)
class SearchIndexResult:
    """Result of a search index operation.

    Represents a single document found in a search index,
    with relevance score and search-specific metadata like highlights.

    This is the search-layer specific result type (different from vector SearchResult).
    Use SearchResult from data.vector for vector database results.
    """

    id: str
    """Unique document identifier."""

    score: float
    """Relevance score (0.0-1.0 typical range)."""

    data: dict[str, Any] = field(default_factory=dict)
    """Original indexed document data."""

    highlights: dict[str, str] | None = None
    """Search term highlights (field -> highlighted text)."""


@dataclass(frozen=True, slots=True)
class SearchableSpec:
    """Specification for search-index-based resource searching.

    Shared across ``quadkit-admin`` (the admin resource opt-in) and
    ``quadkit-search`` (the index-backed execution machinery), so it lives
    in contracts per the shared-type rule.

    Attributes:
        index_name: Name of the search index (defaults to resource name).
        fields: Which fields to include in the searchable document body.
        result_limit: Max results per query.
    """

    index_name: str | None = None
    fields: tuple[str, ...] = ()
    result_limit: int = 50


__all__ = [
    "DocumentData",
    "IndexSettings",
    "SearchFilters",
    "SearchIndexResult",
    "SearchableSpec",
]
