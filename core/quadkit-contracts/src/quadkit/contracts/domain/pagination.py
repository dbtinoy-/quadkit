"""Pagination data models for Quadkit Framework."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class OffsetPageProtocol(Protocol):
    """Protocol for offset-based page request parameters.

    Implemented by offset/limit style pagination inputs.  Use this for
    code that should work with any offset-pagination type.
    """

    @property
    def offset(self) -> int:
        """Zero-based record offset."""
        ...

    @property
    def limit(self) -> int:
        """Maximum number of records to return."""
        ...


@runtime_checkable
class CursorPageProtocol(Protocol, Generic[T]):
    """Protocol for cursor-based paginated result pages.

    Implemented by ``CursorPage`` and Relay-compliant GraphQL page types.
    Use this for code that should work with any cursor-pagination result.
    """

    @property
    def items(self) -> list[T]:
        """Items in this page."""
        ...

    @property
    def next_cursor(self) -> str | None:
        """Opaque cursor for the next page, or ``None`` if no more."""
        ...

    @property
    def has_more(self) -> bool:
        """Whether there are more results after this page."""
        ...


@dataclass(frozen=True)
class CursorPage(Generic[T]):
    """Cursor-based pagination for large datasets.

    Attributes:
        items: The entities in this page.
        next_cursor: Opaque cursor for the next page, or None if no more.
        prev_cursor: Opaque cursor for the previous page, or None.
        has_more: Whether there are more results after this page.
        has_previous: Whether there are results before this page.
        total_count: Optional total count (may be None for performance).
    """

    items: list[T]
    next_cursor: str | None = None
    prev_cursor: str | None = None
    has_more: bool = False
    has_previous: bool = False
    total_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to API-friendly dictionary."""
        return {
            "items": self.items,
            "next_cursor": self.next_cursor,
            "prev_cursor": self.prev_cursor,
            "has_more": self.has_more,
            "has_previous": self.has_previous,
            "total_count": self.total_count,
        }


__all__ = [
    "CursorPage",
    "CursorPageProtocol",
    "OffsetPageProtocol",
    "T",
]
