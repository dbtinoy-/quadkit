"""In-memory session store for development and testing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.auth.models.session import UserSession


class InMemorySessionStore:
    """In-memory session storage for development and testing.

    This store is NOT suitable for production as it does not persist data
    across restarts and does not support multi-instance deployments.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, UserSession] = {}

    async def create(self, session: UserSession) -> str:
        """Create a new session."""
        self._sessions[session.session_id] = session
        return session.session_id

    async def get(self, session_id: str) -> UserSession | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def update(self, session_id: str, **updates: Any) -> None:
        """Update session fields."""
        session = self._sessions.get(session_id)
        if session:
            for key, value in updates.items():
                if hasattr(session, key):
                    object.__setattr__(session, key, value)

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def delete_all_for_user(self, user_id: str) -> int:
        """Delete all sessions for a user."""
        to_delete = [sid for sid, s in self._sessions.items() if s.user_id == user_id]
        for sid in to_delete:
            del self._sessions[sid]
        return len(to_delete)

    async def list_for_user(self, user_id: str) -> list[UserSession]:
        """List all sessions for a user."""
        return [
            s
            for s in self._sessions.values()
            if s.user_id == user_id and s.is_active and not s.is_expired()
        ]


class InMemoryMFAStore:
    """In-memory MFA storage for development and testing.

    This store is NOT suitable for production.
    """

    def __init__(self) -> None:
        self._mfa: dict[str, dict[str, Any]] = {}

    async def get(self, user_id: str) -> dict[str, Any] | None:
        """Get MFA config for a user."""
        return self._mfa.get(user_id)

    async def save(self, mfa_data: dict[str, object]) -> None:
        """Save MFA config for a user."""
        user_id = mfa_data.get("user_id")
        if isinstance(user_id, str):
            self._mfa[user_id] = mfa_data

    async def delete(self, user_id: str) -> bool:
        """Delete MFA config for a user."""
        if user_id in self._mfa:
            del self._mfa[user_id]
            return True
        return False


__all__ = [
    "InMemoryMFAStore",
    "InMemorySessionStore",
]
