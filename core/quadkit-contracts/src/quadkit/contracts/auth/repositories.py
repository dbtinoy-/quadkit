"""RepositoryProtocol protocols for auth-domain persistence.

Zero-dependency contracts. Any package may depend on these without coupling
to a concrete database driver or to each other.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime

__all__ = [
    "APIKeyRepositoryProtocol",
    "SessionRepositoryProtocol",
]


@runtime_checkable
class APIKeyRepositoryProtocol(Protocol):
    """Persistence contract for API key records.

    Implementations are responsible for all SQL/NoSQL I/O.  Business-logic
    callers (e.g. ``APIKeyManager``) depend only on this protocol, keeping
    them decoupled from the underlying data store.
    """

    async def insert(self, payload: dict[str, Any]) -> str:
        """Persist a new API key record and return the generated key_id.

        Args:
            payload: Field/value mapping for the new row (name, key_hash,
                prefix, user_id, scopes, expires_at, …).

        Returns:
            The opaque identifier assigned to the record by the store.
        """
        ...

    async def find_by_prefix(self, prefix: str) -> list[dict[str, Any]]:
        """Return all active (non-revoked) keys whose display prefix matches.

        Args:
            prefix: The short displayable prefix used for fast pre-filtering.

        Returns:
            List of raw row dicts; empty list when nothing matches.
        """
        ...

    async def update_last_used(self, key_id: str, ip_address: str | None) -> None:
        """Refresh the last-used timestamp and originating IP for a key.

        Args:
            key_id: Identifier of the key to update.
            ip_address: Caller IP, or ``None`` when unavailable.
        """
        ...

    async def revoke(self, key_id: str) -> bool:
        """Mark a key as permanently revoked.

        Args:
            key_id: Identifier of the key to revoke.

        Returns:
            ``True`` when a live key was revoked; ``False`` when the id is
            unknown or already revoked.
        """
        ...

    async def find_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return all active (non-revoked) keys for a user.

        Args:
            user_id: Owner identifier.

        Returns:
            List of raw row dicts; empty list when nothing matches.
        """
        ...


@runtime_checkable
class SessionRepositoryProtocol(Protocol):
    """Persistence contract for user session records.

    Decouples session-management business logic from the underlying store,
    allowing SQL, Redis, or any other backend to be injected without
    altering the service layer.
    """

    async def insert(self, payload: dict[str, Any]) -> None:
        """Persist a new session record.

        Args:
            payload: Field/value mapping for the new row (session_id,
                admin_id, device_id, ip_address, user_agent, fingerprint,
                expires_at, …).
        """
        ...

    async def find_active(self, session_id: str) -> dict[str, Any] | None:
        """Return the row for an active session, or ``None`` if absent/inactive.

        Args:
            session_id: The opaque session identifier.

        Returns:
            Raw row dict on success, ``None`` otherwise.
        """
        ...

    async def find_active_by_user(
        self,
        user_id: str,
        cutoff: datetime,
    ) -> list[dict[str, Any]]:
        """Return all non-expired, active sessions for a user.

        Args:
            user_id: The user to query for.
            cutoff: Sessions expiring *at or before* this time are excluded.

        Returns:
            List of raw row dicts ordered by ``last_active_at`` descending.
        """
        ...

    async def revoke(self, session_id: str) -> None:
        """Deactivate a single session.

        Args:
            session_id: Session to revoke.
        """
        ...

    async def revoke_all(self, user_id: str) -> None:
        """Deactivate every active session owned by a user.

        Args:
            user_id: Owner whose sessions are to be revoked.
        """
        ...

    async def update_activity(self, session_id: str, now: datetime) -> None:
        """Refresh the ``last_active_at`` timestamp for an active session.

        Args:
            session_id: Session to touch.
            now: Current UTC timestamp to write.
        """
        ...
