"""Lifecycle hooks for auth/session — intercepted when session operations occur."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "SessionCreatedHook",
    "SessionExpiredHook",
    "SessionRefreshedHook",
    "SessionRevokedHook",
]


@dataclass(frozen=True, kw_only=True)
class SessionCreatedHook:
    """Payload fired when a new session is created.

    Attributes:
        session_id: Unique identifier of the session.
        user_id: Identifier of the user owning the session.
    """

    session_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class SessionRefreshedHook:
    """Payload fired when a session token is refreshed.

    Attributes:
        session_id: Unique identifier of the session being refreshed.
        user_id: Identifier of the user owning the session.
    """

    session_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class SessionExpiredHook:
    """Payload fired when a session expires.

    Attributes:
        session_id: Unique identifier of the expired session.
        user_id: Identifier of the user whose session expired.
    """

    session_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class SessionRevokedHook:
    """Payload fired when a session is explicitly revoked.

    Attributes:
        session_id: Unique identifier of the revoked session.
        user_id: Identifier of the user whose session was revoked.
        reason: Short description of why the session was revoked.
    """

    session_id: str
    user_id: str
    reason: str
