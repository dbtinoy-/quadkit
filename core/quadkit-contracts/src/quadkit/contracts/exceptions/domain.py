"""Domain and business logic exception classes."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class DomainError(QuadkitError):
    """Business/domain-level errors (validation failures, not found, auth)."""

    _code = "QK_ERR_DOM_001"

    def __init__(self, message: str = "Domain error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class NotFoundError(DomainError):
    """Resource not found error (domain-level)."""

    _code = "QK_ERR_DOM_002"

    def __init__(self, message: str = "Not found", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class PermissionDeniedError(DomainError):
    """Permission denied error (domain-level)."""

    _code = "QK_ERR_DOM_003"

    def __init__(self, message: str = "Permission denied", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class AuthenticationError(DomainError):
    """Authentication error (domain-level)."""

    _code = "QK_ERR_DOM_004"

    def __init__(self, message: str = "Authentication failed", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class AuthorizationError(DomainError):
    """Authorization/permission error (domain-level)."""

    _code = "QK_ERR_DOM_005"

    def __init__(self, message: str = "Authorization failed", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class RateLimitError(DomainError):
    """Rate limiting error."""

    _code = "QK_ERR_DOM_006"

    def __init__(self, message: str = "Rate limit exceeded", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class ConflictError(DomainError):
    """Resource conflict error."""

    _code = "QK_ERR_DOM_007"

    def __init__(self, message: str = "Conflict", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class SerializationError(QuadkitError):
    """Serialization/deserialization error."""

    _code = "QK_ERR_SERIAL_001"

    def __init__(self, message: str = "Serialization error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class MappingError(QuadkitError):
    """Object mapping error."""

    _code = "QK_ERR_MAP_001"

    def __init__(self, message: str = "Mapping error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class WebError(DomainError):
    """Web layer error."""

    _code = "QK_ERR_WEB_001"

    def __init__(self, message: str = "Web error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class FieldError(DomainError):
    """A single field-level validation error.

    Used to represent validation failures for individual fields in a domain
    object. Can be returned in a Result or collected in a ValidationError.

    Attributes:
        field: Name of the field that failed validation.
        message: Human-readable description of the failure.
        code: Machine-readable error code for programmatic handling.
    """

    _code = "QK_ERR_VAL_001"

    def __init__(
        self, field: str, message: str, code: str = "INVALID", **kwargs: Any
    ) -> None:
        # Call parent with the field error message - but we'll override message
        super().__init__(f"{field}: {message}", **kwargs)
        # Store field-specific attributes
        self.field = field
        # Override message to be just the field message (for backward compat with dataclass)
        # The parent class message includes "field: message", but we want just "message"
        self._field_message = message
        self.message = message
        # Override code
        self.code = code

    def __repr__(self) -> str:
        return (
            f"FieldError(field={self.field!r}, message={self.message!r}, "
            f"code={self.code!r})"
        )


class ValidationError(DomainError):
    """Data validation error."""

    _code = "QK_ERR_VAL_002"

    def __init__(
        self,
        message: str = "Validation failed",
        errors: list[FieldError] | None = None,
        **kwargs: Any,
    ) -> None:
        if errors:
            kwargs.setdefault("details", {})["errors"] = errors
        super().__init__(message, **kwargs)

    @property
    def errors(self) -> list[FieldError]:
        """Return the list of field errors."""
        from typing import cast

        return cast("list[FieldError]", self.details.get("errors", []))

    def add_error(
        self,
        field: str,
        message: str,
        code: str = "invalid",
    ) -> ValidationError:
        """Add a field error and return self for chaining."""
        if "errors" not in self.details:
            self.details["errors"] = []
        self.details["errors"].append(
            FieldError(field=field, message=message, code=code)
        )
        return self


__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "DomainError",
    "FieldError",
    "MappingError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
    "SerializationError",
    "ValidationError",
    "WebError",
]
