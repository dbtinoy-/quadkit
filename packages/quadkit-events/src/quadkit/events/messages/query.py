"""Query message type for CQRS.

Queries represent requests for data from the read side.
They should not modify any state in the system.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

TResult = TypeVar("TResult")


from quadkit.contracts.events.messages import PaginatedQuery as _PaginatedQuery
from quadkit.contracts.events.messages import Query


class PaginatedQuery(_PaginatedQuery):
    """Query with built-in pagination support."""

    @property
    def offset(self) -> int:
        """Get query offset based on page."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get query limit."""
        return self.page_size


class PagedResult(Generic[TResult]):
    """Container for paginated results.

    Attributes:
        items: The items in the current page.
        total: Total number of items across all pages.
        page: Current page number.
        page_size: Number of items per page.

    Example:
        ```python
        result = PagedResult(
            items=[...],
            total=150,
            page=2,
            page_size=20
        )
        logger.info(result.total_pages)  # 8
        logger.info(result.has_next)  # True
        ```
    """

    def __init__(
        self,
        items: list[TResult],
        total: int,
        page: int,
        page_size: int,
    ) -> None:
        """Initialize paged result.

        Args:
            items: Items in the current page.
            total: Total item count.
            page: Current page number.
            page_size: Items per page.
        """
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size

    @property
    def total_pages(self) -> int:
        """Get total number of pages."""
        return (self.total + self.page_size - 1) // self.page_size

    @property
    def has_next(self) -> bool:
        """Check if there is a next page.

        Returns:
            True if there are more pages after current.
        """
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """Check if there is a previous page.

        Returns:
            True if there are pages before current.
        """
        return self.page > 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation of paged result.
        """
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
            "has_next": self.has_next,
            "has_prev": self.has_prev,
        }


__all__ = ["PagedResult", "PaginatedQuery", "Query"]
