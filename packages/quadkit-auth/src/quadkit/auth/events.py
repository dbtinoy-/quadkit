"""Auth domain events emitted by key authentication operations.

Consumers subscribe via :class:`~quadkit.contracts.events.protocols.EventBusProtocol`.
All events inherit from :class:`~quadkit.contracts.domain.events.DomainEvent` and carry
``event_id``, ``occurred_at``, and optional event-sourcing metadata from the base.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent


@dataclass(frozen=True, init=False)
class UserAuthenticated(DomainEvent):
    """Emitted when a user successfully authenticates.

    Attributes:
        user_id: ID of the authenticated user.
        method: Authentication method used (e.g. ``"password"``).
        ip: Remote IP address of the request, if available.
    """

    user_id: str
    method: str
    ip: str | None = None


@dataclass(frozen=True, init=False)
class AuthenticationFailed(DomainEvent):
    """Emitted when an authentication attempt fails.

    Attributes:
        email: Email that was used in the failed attempt.
        reason: Human-readable reason for the failure.
        ip: Remote IP address of the request, if available.
    """

    email: str
    reason: str
    ip: str | None = None


@dataclass(frozen=True, init=False)
class UserRegistered(DomainEvent):
    """Emitted when a new user account is created.

    Attributes:
        user_id: ID of the newly created user.
        email: Email address of the newly created user.
    """

    user_id: str
    email: str


@dataclass(frozen=True, init=False)
class PasswordChanged(DomainEvent):
    """Emitted when a user successfully changes their password.

    Attributes:
        user_id: ID of the user whose password was changed.
    """

    user_id: str


@dataclass(frozen=True, init=False)
class SessionCreated(DomainEvent):
    """Emitted when a new session/token is issued.

    Attributes:
        session_id: Identifier for the new session.
        user_id: ID of the user who owns the session.
    """

    session_id: str
    user_id: str


@dataclass(frozen=True, init=False)
class SessionRevoked(DomainEvent):
    """Emitted when a session/token is invalidated.

    Attributes:
        session_id: Identifier of the revoked session.
        user_id: ID of the user who owned the session.
    """

    session_id: str
    user_id: str


# ---------------------------------------------------------------------------
# High-fidelity login lifecycle events (G4-A12.2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, init=False)
class UserLoggedIn(DomainEvent):
    """Emitted after a successful password-based login.

    Attributes:
        user_id: ID of the authenticated user.
        email: Email address used to log in.
    """

    user_id: str
    email: str


@dataclass(frozen=True, init=False)
class UserLoginFailed(DomainEvent):
    """Emitted when a login attempt fails due to bad credentials.

    Attributes:
        email: Email address used in the failed attempt.
        reason: Human-readable reason for the failure.
    """

    email: str
    reason: str


@dataclass(frozen=True, init=False)
class UserLockedOut(DomainEvent):
    """Emitted when a login attempt is rejected because the account is locked.

    Attributes:
        user_id: ID of the locked-out user.
        email: Email address of the locked-out user.
    """

    user_id: str
    email: str


@dataclass(frozen=True, init=False)
class UserLoggedOut(DomainEvent):
    """Emitted when a user explicitly logs out.

    Attributes:
        user_id: ID of the user who logged out.
    """

    user_id: str


@dataclass(frozen=True, init=False)
class TokenRevoked(DomainEvent):
    """Emitted when a specific token is revoked.

    Attributes:
        token_id: JTI or opaque identifier of the revoked token.
        user_id: ID of the user who owned the token.
        reason: Human-readable reason for revocation.
    """

    token_id: str
    user_id: str
    reason: str


__all__ = [
    "AuthenticationFailed",
    "PasswordChanged",
    "SessionCreated",
    "SessionRevoked",
    "TokenRevoked",
    "UserAuthenticated",
    "UserLockedOut",
    "UserLoggedIn",
    "UserLoggedOut",
    "UserLoginFailed",
    "UserRegistered",
]
