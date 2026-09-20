"""RFC 7807 Problem Details for HTTP APIs.

Provides standardized error response format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProblemDetail:
    """RFC 7807 Problem Details for HTTP APIs.

    Attributes:
        type: URI identifying the problem type
        title: Short summary of the problem
        status: HTTP status code
        detail: Human-readable explanation
        instance: URI for this specific occurrence
        errors: Additional validation errors (extension)
    """

    type: str = "about:blank"
    title: str = "An error occurred"
    status: int = 500
    detail: str = "An unexpected error occurred"
    instance: str | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
        }
        if self.instance:
            result["instance"] = self.instance
        if self.errors:
            result["errors"] = self.errors
        return result

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        status: int = 500,
        debug: bool = False,
        **kwargs: Any,
    ) -> ProblemDetail:
        """Create a ProblemDetail from an exception.

        When debug is False (default), server-error responses (5xx) use a
        generic detail string to prevent internal information from leaking
        to API consumers.  Set debug=True only in development environments.
        """
        detail = str(exc) if debug or status < 500 else "An unexpected error occurred"
        return cls(
            status=status,
            detail=detail,
            **kwargs,
        )

    @classmethod
    def validation_error(
        cls,
        errors: list[dict[str, Any]],
        detail: str = "Validation failed",
    ) -> ProblemDetail:
        """Create a validation error ProblemDetail."""
        return cls(
            type="urn:quadkit:validation-error",
            title="Validation Error",
            status=400,
            detail=detail,
            errors=errors,
        )

    @classmethod
    def not_found(
        cls,
        resource: str,
        identifier: str | None = None,
    ) -> ProblemDetail:
        """Create a not found ProblemDetail."""
        detail = f"Resource '{resource}' not found"
        if identifier:
            detail += f": {identifier}"
        return cls(
            type="urn:quadkit:not-found",
            title="Not Found",
            status=404,
            detail=detail,
        )

    @classmethod
    def bad_request(
        cls,
        detail: str,
        errors: list[dict[str, Any]] | None = None,
    ) -> ProblemDetail:
        """Create a bad request ProblemDetail."""
        return cls(
            type="urn:quadkit:bad-request",
            title="Bad Request",
            status=400,
            detail=detail,
            errors=errors or [],
        )

    @classmethod
    def internal_error(
        cls,
        detail: str = "An internal error occurred",
    ) -> ProblemDetail:
        """Create an internal error ProblemDetail."""
        return cls(
            type="urn:quadkit:internal-error",
            title="Internal Server Error",
            status=500,
            detail=detail,
        )
