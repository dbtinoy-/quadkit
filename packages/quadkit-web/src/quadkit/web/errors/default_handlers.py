"""RFC 7807 handlers for the failures Starlette answers on its own.

An unknown route or an unsupported method never reaches the filter pipeline:
Starlette raises its own ``HTTPException`` and renders ``text/plain``. A
client written against the framework's ``application/problem+json`` contract
therefore sees a body shape it cannot parse for the two most common client
mistakes. These handlers emit the same media type as every other failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web.errors.problem_detail import ProblemDetail
from quadkit.web.transport.responses import JSONResponse

if TYPE_CHECKING:
    from quadkit.web.transport.responses import Response

#: ``type`` URIs for the framework-generated client errors, matching the
#: ``urn:quadkit:<code>`` convention the filter pipeline uses.
_TYPES = {
    404: "urn:quadkit:not-found",
    405: "urn:quadkit:method-not-allowed",
}

_TITLES = {
    404: "Not Found",
    405: "Method Not Allowed",
}


def _problem_response(status_code: int, detail: str | None, headers: Any) -> Response:
    """Render one Starlette-generated client error as a problem document."""
    return JSONResponse(
        content=ProblemDetail(
            type=_TYPES.get(status_code, "about:blank"),
            title=_TITLES.get(status_code, "Error"),
            status=status_code,
            detail=detail or _TITLES.get(status_code, "Error"),
        ).to_dict(),
        status_code=status_code,
        headers=dict(headers) if headers else None,
        media_type="application/problem+json",
    )


async def not_found_handler(_request: Any, exc: Exception) -> Response:
    """Answer an unmatched path with ``application/problem+json``.

    ``Allow``/``WWW-Authenticate``-style headers carried by the raised
    exception are preserved, so a client still learns what it may do next.
    """
    headers = getattr(exc, "headers", None)
    return _problem_response(404, getattr(exc, "detail", None), headers)


async def method_not_allowed_handler(_request: Any, exc: Exception) -> Response:
    """Answer an unsupported method with ``application/problem+json``."""
    headers = getattr(exc, "headers", None)
    return _problem_response(405, getattr(exc, "detail", None), headers)


def default_error_handlers() -> dict[Any, Any]:
    """Return the exception-handler mapping for Starlette-generated errors."""
    from starlette.exceptions import HTTPException as StarletteHTTPException

    return {
        StarletteHTTPException: _http_exception_handler,
    }


async def _http_exception_handler(request: Any, exc: Exception) -> Response:
    """Route every Starlette-generated HTTP error through the problem shape."""
    status_code = getattr(exc, "status_code", 500)
    headers = getattr(exc, "headers", None)
    return _problem_response(status_code, getattr(exc, "detail", None), headers)


__all__ = [
    "default_error_handlers",
    "method_not_allowed_handler",
    "not_found_handler",
]
