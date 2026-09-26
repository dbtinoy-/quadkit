"""Immutable Query value object and fluent QueryBuilder.

Provides a type-safe, composable way to describe data queries using the
filter algebra and pagination specifications from ``quadkit.contracts.data``.

Example::

    from quadkit.sql.query.builder import QueryBuilder
    from quadkit.contracts.data import FieldEq, SortSpecification

    query = (
        QueryBuilder()
        .filter(FieldEq(field="status", value="active"))
        .order_by("created_at", direction="desc")
        .page(page=1, size=25)
        .build()
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from quadkit.contracts.data.protocols import (
    CursorPaginationSpec,
    FilterExpression,
    PaginationSpec,
    SortSpecification,
)


@dataclass(frozen=True)
class Query:
    """Immutable descriptor for a data query.

    Attributes:
        filter: Optional filter expression to apply.
        sort: Ordered list of sort specifications.
        pagination: Offset-based pagination, or ``None`` for no paging.
        cursor_pagination: Cursor-based pagination, or ``None`` for no cursor paging.
    """

    filter: FilterExpression | None = None
    sort: tuple[SortSpecification, ...] = field(default_factory=tuple)
    pagination: PaginationSpec | None = None
    cursor_pagination: CursorPaginationSpec | None = None


class QueryBuilder:
    """Fluent builder for :class:`Query` instances.

    Each method returns a *new* ``QueryBuilder`` instance, leaving the original
    unchanged, so builders can be safely shared and branched.

    Example::

        base = QueryBuilder().filter(FieldEq("active", True))
        page1 = base.page(page=1, size=10).build()
        page2 = base.page(page=2, size=10).build()
    """

    def __init__(
        self,
        *,
        filter_expr: FilterExpression | None = None,
        sort: tuple[SortSpecification, ...] = (),
        pagination: PaginationSpec | None = None,
        cursor_pagination: CursorPaginationSpec | None = None,
    ) -> None:
        self._filter = filter_expr
        self._sort = sort
        self._pagination = pagination
        self._cursor_pagination = cursor_pagination

    # ------------------------------------------------------------------
    # Filter
    # ------------------------------------------------------------------

    def filter(self, expression: FilterExpression) -> QueryBuilder:
        """Set or replace the filter expression.

        Args:
            expression: The filter expression to apply.

        Returns:
            A new ``QueryBuilder`` with the given filter.
        """
        return QueryBuilder(
            filter_expr=expression,
            sort=self._sort,
            pagination=self._pagination,
            cursor_pagination=self._cursor_pagination,
        )

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def order_by(
        self,
        field_name: str,
        *,
        direction: Literal["asc", "desc"] = "asc",
    ) -> QueryBuilder:
        """Append a sort specification.

        Args:
            field_name: The name of the field to sort by.
            direction: Sort direction — ``"asc"`` (default) or ``"desc"``.

        Returns:
            A new ``QueryBuilder`` with the sort appended.
        """
        spec = SortSpecification(field=field_name, direction=direction)
        return QueryBuilder(
            filter_expr=self._filter,
            sort=(*self._sort, spec),
            pagination=self._pagination,
            cursor_pagination=self._cursor_pagination,
        )

    # ------------------------------------------------------------------
    # Offset pagination
    # ------------------------------------------------------------------

    def page(self, *, page: int = 1, size: int = 20) -> QueryBuilder:
        """Configure offset-based pagination.

        Args:
            page: 1-based page number.
            size: Number of results per page.

        Returns:
            A new ``QueryBuilder`` with offset pagination set.
        """
        return QueryBuilder(
            filter_expr=self._filter,
            sort=self._sort,
            pagination=PaginationSpec(page=page, size=size),
            cursor_pagination=None,
        )

    # ------------------------------------------------------------------
    # Cursor pagination
    # ------------------------------------------------------------------

    def cursor(self, *, cursor: str | None = None, size: int = 20) -> QueryBuilder:
        """Configure cursor-based (keyset) pagination.

        Args:
            cursor: Opaque cursor from a previous response, or ``None`` for
                the first page.
            size: Number of results per page.

        Returns:
            A new ``QueryBuilder`` with cursor pagination set.
        """
        return QueryBuilder(
            filter_expr=self._filter,
            sort=self._sort,
            pagination=None,
            cursor_pagination=CursorPaginationSpec(cursor=cursor, size=size),
        )

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> Query:
        """Construct the immutable :class:`Query` value object.

        Returns:
            A ``Query`` capturing the currently configured filter, sort,
            and pagination settings.
        """
        return Query(
            filter=self._filter,
            sort=self._sort,
            pagination=self._pagination,
            cursor_pagination=self._cursor_pagination,
        )


class SearchQueryBuilder(QueryBuilder):
    """Fluent query builder with explicit search-oriented helpers.

    Extends :class:`QueryBuilder` with :meth:`filter_expr` — a method that
    makes the intent of passing a raw :data:`FilterExpression` explicit
    (rather than letting callers use the more generic :meth:`filter` alias).

    Search-extension packages (``the optional provider``, ``quadkit-sql``) accept
    a :class:`SearchQueryBuilder` or a plain :class:`QueryBuilder` and compile
    the resulting :class:`Query` to backend-specific query syntax via
    ``FilterCompilerProtocol``.

    Example::

        from quadkit.contracts.data import FieldEq
        from quadkit.sql.query import SearchQueryBuilder

        query = (
            SearchQueryBuilder()
            .filter_expr(FieldEq(field="status", value="published"))
            .order_by("published_at", direction="desc")
            .page(page=1, size=20)
            .build()
        )
    """

    def filter_expr(self, expression: FilterExpression) -> SearchQueryBuilder:
        """Apply *expression* as the query filter.

        Semantically equivalent to :meth:`~QueryBuilder.filter` but reads
        more clearly in search contexts where the argument is always a
        ``FilterExpression`` value produced by the filter algebra.

        Args:
            expression: A ``FilterExpression`` (e.g. ``FieldEq``, ``AndExpr``)
                from ``quadkit.contracts.data.protocols``.

        Returns:
            A new :class:`SearchQueryBuilder` with *expression* set as the
            filter.
        """
        updated = self.filter(expression)
        return SearchQueryBuilder(
            filter_expr=updated._filter,
            sort=updated._sort,
            pagination=updated._pagination,
            cursor_pagination=updated._cursor_pagination,
        )


__all__ = ["Query", "QueryBuilder", "SearchQueryBuilder"]
