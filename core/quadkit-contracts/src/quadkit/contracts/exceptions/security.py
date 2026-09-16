"""Security exception classes for the Quadkit Framework.

Defines the exception hierarchy for the security subsystem,
covering guard denials, input sanitization failures, and CORS violations.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class SecurityError(QuadkitError):
    """Base security error for the Quadkit security subsystem."""

    _code = "QK_ERR_SEC_001"

    def __init__(self, message: str = "Security error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class GuardDeniedError(SecurityError):
    """Raised when a GuardChain denies the request.

    Attributes:
        guard: The name or type of the guard that triggered the denial.
        reason: Human-readable reason for the denial, if provided.
    """

    _code = "QK_ERR_SEC_002"

    def __init__(
        self,
        message: str = "Access denied by guard",
        guard: str | None = None,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.guard = guard
        self.reason = reason


class InputSanitizationError(SecurityError):
    """Raised when sanitization fails due to unrecoverable input structure."""

    _code = "QK_ERR_SEC_003"

    def __init__(
        self, message: str = "Input sanitization failed", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


class CORSViolationError(SecurityError):
    """Raised when a request violates the configured CORS policy.

    Attributes:
        origin: The request origin that was rejected.
    """

    _code = "QK_ERR_SEC_004"

    def __init__(
        self,
        message: str = "CORS policy violation",
        origin: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.origin = origin


class SecretAccessError(SecurityError):
    """Raised when the caller lacks permission to access or modify a secret.

    Attributes:
        secret_name: Name of the secret that was denied access.
        operation: The operation that was denied (read, write, delete, etc.).
    """

    _code = "QK_ERR_SEC_005"

    def __init__(
        self,
        secret_name: str,
        operation: str = "read",
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        details["secret_name"] = secret_name
        details["operation"] = operation
        super().__init__(
            message=f"Access denied: cannot {operation} secret '{secret_name}'",
            details=details,
            **kwargs,
        )
        self.secret_name = secret_name
        self.operation = operation


__all__ = [
    "CORSViolationError",
    "GuardDeniedError",
    "InputSanitizationError",
    "SecretAccessError",
    "SecurityError",
]
