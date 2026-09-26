"""Full-text search utilities for quadkit-sql.

Provides dialect-aware full-text search helpers that integrate with
:class:`~quadkit.sql.repositories.generic_repository.GenericRepository`.

Usage::

    from quadkit.sql.search import PostgresFTSQuery, MySQLFTSQuery, full_text_search

    results = await full_text_search(
        provider=db_provider,
        table="articles",
        columns=["title", "body"],
        query="async python",
        dialect="postgres",
        entity_class=Article,
        limit=20,
    )
"""

from __future__ import annotations

from quadkit.sql.search.full_text import (
    FTSDialect,
    FTSResult,
    MySQLFTSQuery,
    PostgresFTSQuery,
    full_text_search,
)

__all__ = [
    "FTSDialect",
    "FTSResult",
    "MySQLFTSQuery",
    "PostgresFTSQuery",
    "full_text_search",
]
