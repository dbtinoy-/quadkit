"""Session store protocols for abstracting session storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.auth.models.session import UserSession


@runtime_checkable
class SessionStore(Protocol):
    """Protocol for session storage backends.

    Implement this protocol to provide custom session storage
    (SQL, Redis, in-memory, etc.).
    """

    async def create(self, session: UserSession) -> str:
        """Create a new session.

        Args:
            session: The session to create.

        Returns:
            The session_id of the created session.
        """
        ...

    async def get(self, session_id: str) -> UserSession | None:
        """Get a session by ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The session if found, None otherwise.
        """
        ...

    async def update(self, session_id: str, **updates: object) -> None:
        """Update session fields.

        Args:
            session_id: The session ID to update.
            **updates: Fields to update.
        """
        ...

    async def delete(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def delete_all_for_user(self, user_id: str) -> int:
        """Delete all sessions for a user.

        Args:
            user_id: The user ID.

        Returns:
            Number of sessions deleted.
        """
        ...

    async def list_for_user(self, user_id: str) -> list[UserSession]:
        """List all sessions for a user.

        Args:
            user_id: The user ID.

        Returns:
            List of active sessions.
        """
        ...


@runtime_checkable
class MFAStore(Protocol):
    """Protocol for MFA storage backends.

    Implement this protocol to provide custom MFA storage
    (SQL, in-memory, etc.).
    """

    async def get(self, user_id: str) -> dict[str, Any] | None:
        """Get MFA config for a user.

        Args:
            user_id: The user ID.

        Returns:
            MFA data if found, None otherwise.
        """
        ...

    async def save(self, mfa_data: dict[str, object]) -> None:
        """Save MFA config for a user.

        Args:
            mfa_data: MFA data to save.
        """
        ...

    async def delete(self, user_id: str) -> bool:
        """Delete MFA config for a user.

        Args:
            user_id: The user ID.

        Returns:
            True if deleted.
        """
        ...


__all__ = [
    "MFAStore",
    "SessionStore",
]
