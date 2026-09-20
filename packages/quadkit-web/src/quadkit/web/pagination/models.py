"""Pagination data models for quadkit-web.

All of the concrete classes used by the public pagination API live here. The
package-level ``__init__`` simply re-exports them for easy imports and keeps
its contents free of implementation logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

from quadkit.contracts.domain.pagination import CursorPage

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

__all__ = [
    "CursorPage",
    "Page",
    "PageRequest",
    "T",
    "cursor_page_to_response",
    "paginated",
]


def cursor_page_to_response(page: CursorPage[Any]) -> dict[str, Any]:
    """Standard envelope format for cursor pagination."""
    return {
        "items": page.items,
        "meta": {
            "next_cursor": page.next_cursor,
            "prev_cursor": page.prev_cursor,
            "has_more": page.has_more,
        },
    }


def paginated(
    page_param: str = "page",
    size_param: str = "size",
    default_page: int = 1,
    default_size: int = 20,
    max_size: int = 100,
) -> Callable[[Callable[..., Any]], Callable[[dict[str, str]], PageRequest]]:
    """Create a paginated request class with custom parameters.

    The returned callable behaves like the original implementation; it is
    merely a convenience helper and is the only piece of logic remaining in
    this module.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[[dict[str, str]], PageRequest]:
        def wrapper(query_params: dict[str, str]) -> PageRequest:
            try:
                page = int(query_params.get(page_param, default_page))
                page = max(1, page)
            except (ValueError, TypeError):
                page = default_page

            try:
                size = int(query_params.get(size_param, default_size))
                size = min(max(1, size), max_size)
            except (ValueError, TypeError):
                size = default_size

            return PageRequest(page=page, size=size)

        return wrapper

    return decorator


@dataclass
class PageRequest:
    """Standard offset-based pagination request.

    This object is independent of any web framework and can be constructed
    manually from query parameters.
    """

    page: int = 1
    size: int = 20
    sort_by: str | None = None
    sort_order: Literal["asc", "desc"] = "asc"

    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        """Limit for database queries."""
        return self.size


@dataclass
class Page(Generic[T]):
    """Standard offset-based pagination response."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int = field(init=False)

    def __post_init__(self) -> None:
        self.pages = (self.total + self.size - 1) // self.size if self.size > 0 else 0

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def next_page(self) -> int | None:
        return self.page + 1 if self.has_next else None

    @property
    def prev_page(self) -> int | None:
        return self.page - 1 if self.has_prev else None

    def to_response(self) -> dict[str, Any]:
        """Standard envelope format."""
        return {
            "items": self.items,
            "meta": {
                "total": self.total,
                "page": self.page,
                "size": self.size,
                "pages": self.pages,
                "has_next": self.has_next,
                "has_prev": self.has_prev,
                "next_page": self.next_page,
                "prev_page": self.prev_page,
            },
        }
