"""Built-in exception filters for Quadkit Web."""

from __future__ import annotations

import dataclasses
from typing import Any

from quadkit.web.errors.html_error_renderer import DebugHtmlErrorRenderer
from quadkit.web.errors.mapping import (
    get_mapping_for_domain_error,
    get_retry_after_header,
)
from quadkit.web.exceptions import (
    DependencyResolutionError,
    HTTPError,
)
from quadkit.web.transport.responses import JSONResponse


class ValidationErrorFilter:
    """Filter for handling Pydantic and Quadkit validation errors."""

    def can_handle(self, exc: Exception) -> bool:
        """Check if exception is a validation error."""
        name = exc.__class__.__name__
        return (
            name in ("ValidationError", "PydanticValidationError")
            or getattr(exc, "code", None) in ("validation_error", "VALIDATION_ERROR")
            or (
                isinstance(exc, ValueError)
                and any(kw in str(exc) for kw in ("validation", "Invalid", "coercion"))
            )
        )

    async def handle(self, exc: Any, _request: Any) -> JSONResponse:
        """Transform ValidationError into a 422 JSONResponse with RFC 7807 format."""
        raw_errors: list[Any] = []
        if hasattr(exc, "errors") and callable(exc.errors):
            raw_errors = exc.errors()
        elif hasattr(exc, "errors") and isinstance(exc.errors, list):
            raw_errors = exc.errors
        elif hasattr(exc, "args") and exc.args:
            raw_errors = [{"msg": str(arg)} for arg in exc.args]

        errors = []
        for e in raw_errors:
            if dataclasses.is_dataclass(e) and not isinstance(e, type):
                errors.append(dataclasses.asdict(e))
            elif isinstance(e, dict):
                errors.append(e)
            elif hasattr(e, "field") and hasattr(e, "message"):
                errors.append(
                    {
                        "field": e.field,
                        "message": e.message,
                        "code": getattr(e, "code", None),
                    }
                )
            else:
                errors.append({"msg": str(e)})

        from quadkit.web.errors.problem_detail import ProblemDetail

        pd = ProblemDetail(
            type="urn:quadkit:validation-error",
            title="Validation Error",
            status=422,
            detail="Request validation failed",
            errors=errors,
        )
        return JSONResponse(
            content=pd.to_dict(),
            status_code=422,
            media_type="application/problem+json",
        )


class DependencyResolutionFilter:
    """Filter for handling DependencyResolutionError."""

    def can_handle(self, exc: Exception) -> bool:
        """Check if exception is a DependencyResolutionError."""
        return (
            isinstance(exc, DependencyResolutionError)
            or exc.__class__.__name__ == "DependencyResolutionError"
            or getattr(exc, "code", None) == "dependency_resolution_error"
        )

    async def handle(self, exc: Any, _request: Any) -> JSONResponse:
        """Transform DependencyResolutionError into a 500 RFC 7807 JSONResponse."""
        from quadkit.web.errors.problem_detail import ProblemDetail

        pd = ProblemDetail.internal_error(detail=getattr(exc, "detail", str(exc)))
        return JSONResponse(
            content=pd.to_dict(),
            status_code=500,
            media_type="application/problem+json",
        )


class DefaultExceptionFilter:
    """Default filter that handles HTTPError and generic exceptions.

    When ``debug=True`` and the HTTP client sends ``Accept: text/html``,
    the response is a rich HTML error page showing the traceback and request
    details.  In all other cases a structured JSON response is returned.

    This filter now uses the shared mapping from
    ``quadkit.web.errors.mapping`` — the single source of truth for the
    error gateway — so the throw path and the Result-return path always
    agree on status codes. Custom ``ResultResponseMapper.register``/
    ``@error_status`` mappings apply to the Result-return path only, by
    design: a raised custom error resolves through its nearest contract
    base class here.
    """

    def __init__(self, debug: bool = False) -> None:
        """Initialise the filter.

        Args:
            debug: When ``True``, HTML error pages are rendered for browser
                clients.  Set this based on ``ServerConfig.debug`` or
                the ``QK_DEBUG`` environment variable.
        """
        self._debug = debug
        self._html_renderer = DebugHtmlErrorRenderer()

    def can_handle(self, exc: Exception) -> bool:
        """Handle HTTPErrors and QuadkitErrors specifically."""
        from quadkit.contracts.exceptions import QuadkitError

        return (
            isinstance(exc, (HTTPError, QuadkitError))
            or getattr(exc, "status_code", None) is not None
            or hasattr(exc, "code")
        )

    async def handle(self, exc: Exception, request: Any) -> Any:
        """Transform the exception into a JSON or HTML response.

        When ``debug=True`` and the request prefers HTML, a rich debug page
        is returned instead of JSON.  All JSON responses use RFC 7807
        ``application/problem+json`` format.
        """
        from quadkit.web.errors.problem_detail import ProblemDetail

        if isinstance(exc, HTTPError):
            if self._debug and self._html_renderer.should_render(request):
                return self._html_renderer.render(
                    exc,
                    request,
                    status_code=exc.status_code,
                    title=f"{exc.status_code} {exc.detail}",
                )
            code = getattr(exc, "code", None)
            pd = ProblemDetail(
                type=(
                    f"urn:quadkit:{code.lower().replace('_', '-')}"
                    if code
                    else "about:blank"
                ),
                title=exc.detail,
                status=exc.status_code,
                detail=exc.detail,
            )
            return JSONResponse(
                content=pd.to_dict(),
                status_code=exc.status_code,
                headers=exc.headers,
                media_type="application/problem+json",
            )

        # Handle domain errors via shared mapping — single source of truth
        mapping = get_mapping_for_domain_error(exc)
        if mapping is not None:
            status_code, type_uri, title = mapping
            headers = get_retry_after_header(exc)
        else:
            # Fallback: status_code attribute or 500
            status_code = getattr(exc, "status_code", 500)
            try:
                status_code = int(status_code)
            except (TypeError, ValueError):
                status_code = 500
            # Only domain errors that slipped through should be 400;
            # everything else is 500. get_mapping_for_domain_error already
            # covered DomainError, so remaining 400s are via status_code attr.
            from quadkit.contracts.exceptions.domain import DomainError

            if status_code == 500 and isinstance(exc, DomainError):
                status_code = 400
            type_uri = (
                "urn:quadkit:internal-error"
                if status_code >= 500
                else "urn:quadkit:bad-request"
            )
            title = "Internal Server Error" if status_code >= 500 else "Bad Request"
            headers = get_retry_after_header(exc)

        if self._debug and self._html_renderer.should_render(request):
            return self._html_renderer.render(exc, request, status_code=status_code)

        # For 5xx, hide details unless debug — prevent internal leakage
        detail = (
            str(exc)
            if self._debug or status_code < 500
            else "An unexpected error occurred"
        )
        # But for domain errors (4xx), always show message
        from quadkit.contracts.exceptions.domain import DomainError

        if isinstance(exc, DomainError):
            detail = str(exc)

        pd = ProblemDetail(
            type=type_uri,
            title=title,
            status=status_code,
            detail=detail,
        )
        return JSONResponse(
            content=pd.to_dict(),
            status_code=status_code,
            headers=headers,
            media_type="application/problem+json",
        )


__all__ = [
    "DefaultExceptionFilter",
    "DependencyResolutionFilter",
    "ValidationErrorFilter",
]
