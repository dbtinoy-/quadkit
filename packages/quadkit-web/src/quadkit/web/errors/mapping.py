"""Shared error-to-HTTP mapping — single source of truth for the error gateway.

This module owns the mapping from domain exceptions to HTTP status codes,
URN type URIs and titles. Both the Result-return path (ResultResponseMapper)
and the throw path (DefaultExceptionFilter) must agree on the same status
for the same contract error. Previously they duplicated the table; now they
both import from here.

Registry lifetime: module-level, process-wide. Registrations are startup
wiring — perform them at import time, before serving.
"""

from __future__ import annotations

import re
from typing import Any, cast

from quadkit.contracts.exceptions.domain import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Core registry — error type → HTTP status
# ---------------------------------------------------------------------------

_ERROR_STATUS_REGISTRY: list[tuple[type[Exception], int]] = [
    (NotFoundError, 404),
    (ValidationError, 422),
    (PermissionDeniedError, 403),
    (AuthorizationError, 403),
    (AuthenticationError, 401),
    (ConflictError, 409),
    (RateLimitError, 429),
    (DomainError, 400),
]

# ---------------------------------------------------------------------------
# URN / title table — mirrors status registry for RFC 7807 responses
# ---------------------------------------------------------------------------

_STATUS_TYPE_TITLE: dict[int, tuple[str, str]] = {
    400: ("urn:quadkit:bad-request", "Bad Request"),
    401: ("urn:quadkit:unauthorized", "Unauthorized"),
    403: ("urn:quadkit:forbidden", "Forbidden"),
    404: ("urn:quadkit:not-found", "Not Found"),
    405: ("urn:quadkit:method-not-allowed", "Method Not Allowed"),
    409: ("urn:quadkit:conflict", "Conflict"),
    422: ("urn:quadkit:validation-error", "Validation Error"),
    429: ("urn:quadkit:too-many-requests", "Too Many Requests"),
    500: ("urn:quadkit:internal-error", "Internal Server Error"),
}

# Precise mapping for known domain errors — used by DefaultExceptionFilter
_DOMAIN_ERROR_MAP: list[tuple[type[Exception], int, str, str]] = [
    (NotFoundError, 404, "urn:quadkit:not-found", "Not Found"),
    (PermissionDeniedError, 403, "urn:quadkit:forbidden", "Forbidden"),
    (AuthorizationError, 403, "urn:quadkit:forbidden", "Forbidden"),
    (AuthenticationError, 401, "urn:quadkit:unauthorized", "Unauthorized"),
    (ConflictError, 409, "urn:quadkit:conflict", "Conflict"),
    (RateLimitError, 429, "urn:quadkit:too-many-requests", "Too Many Requests"),
    (ValidationError, 422, "urn:quadkit:validation-error", "Validation Error"),
    (DomainError, 400, "urn:quadkit:bad-request", "Bad Request"),
]


def _exception_type_urn(exc: Exception) -> str:
    """Derive a urn:quadkit:{slug} type URI from an exception class name."""
    name = type(exc).__name__
    for suffix in ("Error", "Exception"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    slug = re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()
    return f"urn:quadkit:{slug}"


def get_status_for_error(error: Exception) -> int:
    """Return HTTP status for an error, MRO-aware.

    Checks:
    1. ``status_code`` attribute (web framework errors, GatewayError)
    2. Registry mapping by exception type
    3. ``DomainError`` → 400, else 500
    """
    if hasattr(error, "status_code"):
        try:
            return int(cast("Any", error).status_code)
        except (TypeError, ValueError, AttributeError):
            pass

    for error_type, status in _ERROR_STATUS_REGISTRY:
        if isinstance(error, error_type):
            return status

    return 400 if isinstance(error, DomainError) else 500


def get_type_title_for_status(status: int) -> tuple[str, str]:
    """Return (type_uri, title) for a status code, with fallback."""
    return _STATUS_TYPE_TITLE.get(status, ("about:blank", "Error"))


def get_mapping_for_domain_error(exc: Exception) -> tuple[int, str, str] | None:
    """Return (status, type_uri, title) for a known domain error, or None.

    Walks ``_DOMAIN_ERROR_MAP`` in order, using ``isinstance`` so subclasses
    match their nearest base.
    """
    for err_type, status, type_uri, title in _DOMAIN_ERROR_MAP:
        if isinstance(exc, err_type):
            return status, type_uri, title
    return None


def register_error_status(error_type: type[Exception], status_code: int) -> None:
    """Register custom error → status, taking precedence over defaults."""
    _ERROR_STATUS_REGISTRY.insert(0, (error_type, status_code))


def get_retry_after_header(exc: Exception) -> dict[str, str] | None:
    """Extract Retry-After header from a RateLimitError if present.

    Supports both ``details.retry_after`` (framework) and a direct
    ``retry_after`` attribute (direct-attribute style).
    """
    # Direct attribute style
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        return {"Retry-After": str(retry_after)}

    # Framework style: details dict
    if isinstance(exc, RateLimitError):
        details = getattr(exc, "details", None)
        if isinstance(details, dict):
            retry_after = details.get("retry_after")
            if retry_after is not None:
                return {"Retry-After": str(retry_after)}

    return None


__all__ = [
    "_ERROR_STATUS_REGISTRY",
    "_STATUS_TYPE_TITLE",
    "get_mapping_for_domain_error",
    "get_retry_after_header",
    "get_status_for_error",
    "get_type_title_for_status",
    "register_error_status",
]
