"""Search protocols and data models."""

from __future__ import annotations

from quadkit.contracts.search.protocols import (
    DatabaseSearchBackendProtocol,
    DocumentTransformerProtocol,
    IndexManagerProtocol,
    SearchableProtocol,
    SearchAnalyticsProtocol,
    SearchEngineProtocol,
)
from quadkit.contracts.search.types import (
    DocumentData,
    IndexSettings,
    SearchableSpec,
    SearchFilters,
    SearchIndexResult,
)

__all__ = [
    "DatabaseSearchBackendProtocol",
    "DocumentData",
    "DocumentTransformerProtocol",
    "IndexManagerProtocol",
    "IndexSettings",
    "SearchAnalyticsProtocol",
    "SearchEngineProtocol",
    "SearchFilters",
    "SearchIndexResult",
    "SearchableProtocol",
    "SearchableSpec",
]
