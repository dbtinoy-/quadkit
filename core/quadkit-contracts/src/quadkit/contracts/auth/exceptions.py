"""Auth domain base error hierarchy.

These are the base exception types that any package can catch at the
auth-domain boundary without depending on ``quadkit-auth``.

Infrastructure failures (cache down, network errors, configuration errors)
must still be raised as exceptions — do not wrap them in ``Result``.

Leaf exceptions (``InvalidCredentialsError``, ``TokenExpiredError``, etc.)
live in ``quadkit.auth.exceptions`` — import from there when you need to
distinguish specific auth failure modes.

Error hierarchy
---------------
::

    AuthError          Base for all auth-domain failures
    TokenError         Base for all expected token failures
    VerificationError  Base for all account-verification failures
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.domain import DomainError


class AuthError(DomainError):
    """Base exception for all auth-domain errors.

    This is the catch-all for authentication and authorization failures
    that clients are expected to handle gracefully.
    """

    _code = "QK_ERR_AUTH_001"

    def __init__(
        self,
        message: str = "Auth error",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class TokenError(DomainError):
    """Base class for expected, recoverable token domain failures.

    All subtypes indicate situations the caller is expected to handle
    gracefully (e.g. reject the request, ask for re-authentication).
    """

    _code = "QK_ERR_AUTH_002"

    def __init__(
        self,
        message: str = "Token error",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class VerificationError(DomainError):
    """Base class for expected, recoverable account-verification failures.

    All subtypes signal situations the caller should handle gracefully
    (e.g. redirect to a re-verification page or surface a user-facing error).
    """

    _code = "QK_ERR_AUTH_003"

    def __init__(
        self,
        message: str = "Account verification error",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


__all__ = [
    "AuthError",
    "TokenError",
    "VerificationError",
]
