"""Standard HTTP response envelope types for Quadkit Framework.

Provides consistent, type-safe data structures for common HTTP response
patterns: error responses and paginated result sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ErrorDetail:
    """Single error detail in an HTTP error response.

    Attributes:
        code: Machine-readable error code (e.g., "INVALID_INPUT").
        message: Human-readable error message.
        field: Optional field name that caused the error (for form validation).
    """

    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class ErrorResponseDTO:
    """Standard HTTP error response envelope.

    Provides a consistent structure for error responses across all endpoints.
    Should be used with appropriate HTTP status codes (4xx, 5xx).

    Attributes:
        error: High-level error category.
        message: Human-readable summary of what went wrong.
        details: List of specific error details (empty for simple errors).
        request_id: Optional request identifier for tracing and support.
    """

    error: str
    message: str
    details: list[ErrorDetail] = field(default_factory=list)
    request_id: str | None = None


@dataclass(frozen=True)
class PaginatedResponseDTO(Generic[T]):
    """Standard paginated HTTP response envelope.

    Encapsulates a page of results with metadata for navigation.
    Supports both offset-based and cursor-based pagination.

    Attributes:
        items: The entities in this page.
        total: Total count of items across all pages.
        page: Current page number (1-indexed, 0-indexed for cursor).
        page_size: Maximum items returned per page.
        has_next: Whether there are more pages after this one.
        has_prev: Whether there are pages before this one.
        next_cursor: Opaque cursor for the next page (for cursor-based pagination).
    """

    items: list[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
    next_cursor: str | None = None


__all__ = [
    "ErrorDetail",
    "ErrorResponseDTO",
    "PaginatedResponseDTO",
]
