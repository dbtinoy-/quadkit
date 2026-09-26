"""Exception hierarchy for Quadkit Auth.

All exceptions are organized by inheritance level:
1. Re-imports from quadkit-contracts (base classes, aliased into this hierarchy)
2. Auth root exception
3. Authentication exceptions (credentials, tokens, account)
4. Authorization exceptions
5. Verification exceptions
6. Registration/conflict exceptions
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.auth.exceptions import AuthError as ContractsAuthError
from quadkit.contracts.auth.exceptions import VerificationError
from quadkit.contracts.exceptions import (
    AuthenticationError as QuadkitAuthenticationError,
)
from quadkit.contracts.exceptions import (
    AuthorizationError as QuadkitAuthorizationError,
)
from quadkit.contracts.exceptions import (
    ConflictError,
)
from quadkit.contracts.exceptions import (
    NotFoundError as QuadkitNotFoundError,
)


class AuthError(ContractsAuthError):
    """Base exception for all auth errors."""

    _code = "QK_ERR_AUTH_004"


class AuthenticationError(QuadkitAuthenticationError, AuthError):
    """Raised when authentication fails."""

    _code = "QK_ERR_AUTH_005"


class AuthorizationError(QuadkitAuthorizationError, AuthError):
    """Raised when user lacks required permissions."""

    _code = "QK_ERR_AUTH_006"


class InvalidCredentialsError(AuthenticationError):
    """Raised when credentials are invalid."""

    _code = "QK_ERR_AUTH_007"

    def __init__(self, message: str = "Invalid credentials", **kwargs: Any):
        super().__init__(message, **kwargs)


class AccountLockedError(AuthenticationError):
    """Raised when an account is locked due to too many failed login attempts.

    Accounts are locked automatically after ``LockoutConfig.max_failed_attempts``
    consecutive failures within ``LockoutConfig.lockout_duration_seconds``.
    The lock is lifted automatically once the observation window has passed.
    """

    _code = "QK_ERR_AUTH_008"

    def __init__(self, email: str = "", **kwargs: Any):
        msg = (
            f"Account locked due to too many failed login attempts: {email}"
            if email
            else "Account locked due to too many failed login attempts"
        )
        super().__init__(msg, **kwargs)


class UserNotFoundError(QuadkitNotFoundError, AuthError):
    """Raised when user is not found."""

    _code = "QK_ERR_AUTH_009"

    def __init__(self, identifier: str, **kwargs: Any):
        super().__init__(
            f"User not found: {identifier}",
            **kwargs,
        )


class TokenError(InvalidCredentialsError):
    """Base exception for token-related errors."""

    _code = "QK_ERR_AUTH_010"


class InvalidTokenError(TokenError):
    """Raised when a token is malformed or invalid."""

    _code = "QK_ERR_AUTH_011"


class TokenExpiredError(TokenError):
    """Raised when a token has expired."""

    _code = "QK_ERR_AUTH_012"

    def __init__(
        self,
        message: str = "Token has expired",
        expiration_time: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if expiration_time:
            details["expiration_time"] = expiration_time
        kwargs["details"] = details
        super().__init__(message, **kwargs)


class TokenBlacklistedError(TokenError):
    """Token has been explicitly revoked."""

    _code = "QK_ERR_AUTH_013"

    def __init__(
        self,
        message: str = "Token has been revoked",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class TokenInvalidError(TokenError):
    """Token is structurally invalid or has wrong type."""

    _code = "QK_ERR_AUTH_014"

    def __init__(
        self,
        message: str = "Token is invalid",
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if reason:
            details["reason"] = reason
        kwargs["details"] = details
        super().__init__(message, **kwargs)


class TokenAudienceError(TokenError):
    """Token audience claim does not match expected."""

    _code = "QK_ERR_AUTH_015"

    def __init__(
        self,
        message: str = "Token audience mismatch",
        expected: str | None = None,
        actual: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if expected:
            details["expected"] = expected
        if actual:
            details["actual"] = actual
        kwargs["details"] = details
        super().__init__(message, **kwargs)


class TokenNotFoundError(TokenError):
    """Token record does not exist."""

    _code = "QK_ERR_AUTH_016"

    def __init__(
        self,
        message: str = "Token not found",
        token_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if token_id:
            details["token_id"] = token_id
        kwargs["details"] = details
        super().__init__(message, **kwargs)


class InvalidAudienceError(TokenError):
    """Raised when a token audience is invalid."""

    _code = "QK_ERR_AUTH_017"


class InvalidScopeError(TokenError):
    """Raised when a token lacks required scope."""

    _code = "QK_ERR_AUTH_018"


class BlacklistedTokenError(TokenError):
    """Raised when a token has been blacklisted."""

    _code = "QK_ERR_AUTH_019"


class TokenExpiredVerificationError(VerificationError):
    """Account verification has expired."""

    _code = "QK_ERR_AUTH_020"

    def __init__(
        self,
        message: str = "Verification has expired",
        user_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if user_id:
            details["user_id"] = user_id
        kwargs["details"] = details
        super().__init__(message, **kwargs)


class AlreadyVerifiedError(VerificationError):
    """Account is already verified."""

    _code = "QK_ERR_AUTH_021"

    def __init__(
        self,
        message: str = "Account is already verified",
        user_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if user_id:
            details["user_id"] = user_id
        kwargs["details"] = details
        super().__init__(message, **kwargs)


class EmailExistsError(AuthError, ConflictError):
    """Raised when email is already taken."""

    _code = "QK_ERR_AUTH_022"


class UsernameExistsError(AuthError, ConflictError):
    """Raised when username is already taken."""

    _code = "QK_ERR_AUTH_023"


class PasswordPolicyError(AuthError):
    """Raised when password doesn't meet requirements."""

    _code = "QK_ERR_AUTH_024"


class OAuth2Error(AuthError):
    """Base exception for OAuth2 errors."""

    _code = "QK_ERR_AUTH_025"


class SessionNotFoundError(QuadkitNotFoundError, AuthError):
    """Raised when a session cannot be found in the store."""

    _code = "QK_ERR_AUTH_026"

    def __init__(self, session_id: str, **kwargs: Any):
        super().__init__(
            f"Session not found: {session_id}",
            **kwargs,
        )


__all__ = [
    "AccountLockedError",
    "AlreadyVerifiedError",
    "AuthError",
    "AuthenticationError",
    "AuthorizationError",
    "BlacklistedTokenError",
    "EmailExistsError",
    "InvalidAudienceError",
    "InvalidCredentialsError",
    "InvalidScopeError",
    "InvalidTokenError",
    "OAuth2Error",
    "PasswordPolicyError",
    "SessionNotFoundError",
    "TokenAudienceError",
    "TokenBlacklistedError",
    "TokenError",
    "TokenExpiredError",
    "TokenExpiredVerificationError",
    "TokenInvalidError",
    "TokenNotFoundError",
    "UserNotFoundError",
    "UsernameExistsError",
    "VerificationError",
]
