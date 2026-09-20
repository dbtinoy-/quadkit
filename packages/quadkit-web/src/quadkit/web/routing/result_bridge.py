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

Policy boundary: this module owns error→status mapping for the
Result-return path only. The throw path (``raise`` inside a handler) is
owned by ``DefaultExceptionFilter`` (web.filters.builtin), which covers
the built-in contract error families and does not read the registry
below. The two paths agree on the seven built-in families, so the same
contract error yields the same status in either style; a custom
``register``/``@error_status`` mapping applies to Result-returning
handlers only.

Registry lifetime: ``_ERROR_STATUS_REGISTRY`` is module-level and
process-wide. Registrations are startup wiring — perform them at import
time, before the application begins serving, so every host and worker in
the process observes the same mapping.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

from quadkit.web.errors.mapping import (
    _ERROR_STATUS_REGISTRY,
    _exception_type_urn,
    get_status_for_error,
    register_error_status,
)

if TYPE_CHECKING:
    from starlette.responses import Response


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


# Backward-compat aliases — old code imported these from here
_get_status = get_status_for_error


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
        register_error_status(error_type, status_code)

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

        status = get_status_for_error(error) if isinstance(error, Exception) else 400

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


__all__ = [
    "ResultResponseMapper",
    "_ERROR_STATUS_REGISTRY",
    "_exception_type_urn",
    "_get_status",
    "error_status",
    "get_status_for_error",
]
