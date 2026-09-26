"""Request and response context types for the quadkit.http module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class RequestContext:
    """Context information for an outbound HTTP request.

    Used by interceptors to inspect and modify the request before it is sent.

    Attributes:
        method: HTTP method (upper-cased).
        url: Target URL.
        headers: Request headers as a plain dict.
        service_name: Logical service name if known (service-mesh use cases).
        attempt: Current retry attempt number (0-indexed).
        start_time: Timestamp when the request was initiated.
    """

    method: str
    url: str
    headers: dict[str, str]
    service_name: str | None = None
    attempt: int = 0
    start_time: datetime | None = None

    def __post_init__(self) -> None:
        """Initialise computed fields."""
        if self.start_time is None:
            self.start_time = datetime.now(UTC)


@dataclass
class ResponseContext:
    """Context information for a received HTTP response.

    Used by interceptors to inspect response metadata.

    Attributes:
        status: HTTP status code.
        headers: Response headers.
        content_length: Optional response body length in bytes.
        duration: Round-trip duration in seconds.
        success: ``True`` when ``status < 400``.
        error: Human-readable error message when the request failed.
    """

    status: int
    headers: dict[str, str]
    content_length: int | None = None
    duration: float | None = None
    success: bool = True
    error: str | None = None


__all__ = [
    "RequestContext",
    "ResponseContext",
]
