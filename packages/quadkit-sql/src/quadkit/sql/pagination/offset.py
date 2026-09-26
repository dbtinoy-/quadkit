"""Offset-based pagination result and paginator.

Provides a generic ``Page[T]`` result type and an ``OffsetPaginator`` helper
that slices an in-memory sequence.  For production, backend packages implement
pagination at the query layer (e.g. SQL LIMIT/OFFSET).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    """A single page of offset-based query results.

    Attributes:
        items: Entities on this page.
        total: Total number of matching entities across all pages.
        page: 1-based current page number.
        size: Maximum items per page.
        pages: Total number of pages.
        has_next: Whether a next page exists.
        has_prev: Whether a previous page exists.
    """

    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        """Total number of pages."""
        if self.size == 0:
            return 0
        return ceil(self.total / self.size)

    @property
    def has_next(self) -> bool:
        """Whether a next page exists."""
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        """Whether a previous page exists."""
        return self.page > 1


class OffsetPaginator(Generic[T]):
    """Slices an in-memory list into :class:`Page` results.

    Intended for use in the in-memory repository and tests.  SQL-backed
    repositories should push LIMIT/OFFSET into the query instead.

    Example::

        paginator = OffsetPaginator[User]()
        page = paginator.paginate(all_users, page=2, size=10)
    """

    def paginate(self, items: list[T], *, page: int = 1, size: int = 20) -> Page[T]:
        """Slice *items* and return a :class:`Page`.

        Args:
            items: The full ordered collection to paginate.
            page: 1-based page number.
            size: Maximum number of items per page.

        Returns:
            A ``Page`` covering the requested slice.
        """
        total = len(items)
        start = (page - 1) * size
        end = start + size
        return Page(items=items[start:end], total=total, page=page, size=size)


__all__ = ["OffsetPaginator", "Page"]
