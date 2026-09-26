from __future__ import annotations

from abc import ABC

from quadkit.sql.middleware.models import QueryContext


class QueryMiddleware(ABC):
    """Abstract base for query middleware."""

    async def before_query(self, ctx: QueryContext) -> None:
        """Called before query execution. Override to modify or log."""

    async def after_query(self, ctx: QueryContext) -> None:
        """Called after query execution. Override to observe or log."""
