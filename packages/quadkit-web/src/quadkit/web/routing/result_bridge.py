"""Result-to-HTTP response mapper.

Converts ``Result[T, E]`` domain errors to appropriate HTTP status codes,
allowing controller methods to return typed domain errors without manual
HTTP mapping.

Usage::

    # Register a custom mapping
    ResultResponseMapper.register(MyConflictError, 409)

    # In a controller (handled automatically by the serialization pipeline):
    @get("/{user_id}")
    async def get_user(self, user_id: str) -> Result[User, NotFoundError]:
        return await self.service.find(user_id)
        # If Err(NotFoundError(...)) → HTTP 404
        # If Ok(user) → HTTP 200 with serialized user
"""

from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING, Any, cast

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

if TYPE_CHECKING:
    from starlette.responses import Response

# Registry: error type → HTTP status code
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


def _serialize_details(value: Any) -> Any:
    """Recursively convert dataclass instances to plain dicts for JSON safety."""
    import dataclasses

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return {k: _serialize_details(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_details(item) for item in value]
    return value


def _get_status(error: Exception) -> int:
    """Return the HTTP status code for an error, using MRO-aware lookup.

    Checks:
    1. HTTPError.status_code attribute (web framework errors)
    2. Registry mapping by exception type
    3. ``DomainError`` subclasses → 400 (client fault);
       anything else → 500 (server fault)
    """
    # Check for HTTPError.status_code attribute first (web framework errors)
    if hasattr(error, "status_code"):
        return cast("int", error.status_code)

    # Check registry for domain errors (contracts exceptions)
    for error_type, status in _ERROR_STATUS_REGISTRY:
        if isinstance(error, error_type):
            return status

    # Domain errors not in the registry are client faults; everything else
    # is an unexpected server-side failure and must not read as 4xx.
    return 400 if isinstance(error, DomainError) else 500


def _exception_type_urn(exc: Exception) -> str:
    """Derive a urn:quadkit:{slug} type URI from an exception class name."""
    name = type(exc).__name__
    for suffix in ("Error", "Exception"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    slug = re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()
    return f"urn:quadkit:{slug}"


class ResultResponseMapper:
    """Maps ``Result`` error values to HTTP responses.

    The default mappings follow REST conventions:

    | Error type               | Status |
    |--------------------------|--------|
    | ``NotFoundError``        | 404    |
    | ``ValidationError``      | 422    |
    | ``PermissionDeniedError``| 403    |
    | ``AuthorizationError``   | 403    |
    | ``AuthenticationError``  | 401    |
    | ``ConflictError``        | 409    |
    | ``RateLimitError``       | 429    |
    | ``DomainError`` (base)   | 400    |
    | other ``DomainError``    | 400 (client fault) |
    | non-domain error         | 500 (server fault) |

    Use :meth:`register` to override the status for a specific error type.
    """

    def to_response(self, result: Any, success_status: int = 200) -> Response:
        """Convert a Result to an HTTP response.

        Args:
            result: The ``Result[T, E]`` object to map.
            success_status: HTTP status code for Ok results (default 200).

        Returns:
            A :class:`~quadkit.web.transport.responses.JSONResponse` with
            appropriate status code and structured body.
        """

        from quadkit.web.transport.responses import JSONResponse

        if hasattr(result, "is_ok") and callable(result.is_ok):
            if result.is_ok():
                return JSONResponse(content=result.unwrap(), status_code=success_status)
            return self.error_to_response(result.unwrap_err())

        return JSONResponse(content={"error": "Invalid result object"}, status_code=400)

    @classmethod
    def register(cls, error_type: type[Exception], status_code: int) -> None:
        """Register a custom error type → HTTP status mapping.

        Custom registrations take precedence over defaults (inserted at front).

        Args:
            error_type: The exception class to match.
            status_code: HTTP status code to return.
        """
        _ERROR_STATUS_REGISTRY.insert(0, (error_type, status_code))

    @classmethod
    def error_to_response(cls, error: Any) -> Response:
        """Convert a domain error to a JSON HTTP response.

        Args:
            error: The error value from ``Result.unwrap_err()``.

        Returns:
            A :class:`~quadkit.web.transport.responses.JSONResponse` with the
            appropriate status code and a structured body.
        """

        from quadkit.web.errors.problem_detail import ProblemDetail
        from quadkit.web.transport.responses import JSONResponse

        status = _get_status(error) if isinstance(error, Exception) else 400

        if isinstance(error, Exception):
            pd = ProblemDetail.from_exception(
                error, status=status, type=_exception_type_urn(error)
            )
            # Populate errors[] from ValidationError.errors (FieldError list)
            field_errors = getattr(error, "errors", None)
            if isinstance(field_errors, list) and field_errors:
                serialized = []
                for fe in field_errors:
                    if hasattr(fe, "field") and hasattr(fe, "message"):
                        serialized.append(
                            {
                                "field": fe.field,
                                "message": fe.message,
                                "code": getattr(fe, "code", None),
                            }
                        )
                    elif isinstance(fe, dict):
                        serialized.append(fe)
                if serialized:
                    pd = dataclasses.replace(pd, errors=serialized)
        else:
            pd = ProblemDetail(status=status, detail=str(error))

        return JSONResponse(
            content=pd.to_dict(),
            status_code=status,
            media_type="application/problem+json",
        )


def error_status(error_type: type[Exception], status_code: int) -> Any:
    """Decorator to register a custom error → HTTP status mapping.

    Args:
        error_type: Exception class to match.
        status_code: HTTP status code to use.

    Example::

        @error_status(PaymentDeclined, 402)
        class BillingController(Controller):
            ...
    """

    def decorator(cls_or_fn: Any) -> Any:
        ResultResponseMapper.register(error_type, status_code)
        return cls_or_fn

    return decorator


__all__ = ["ResultResponseMapper", "error_status"]
