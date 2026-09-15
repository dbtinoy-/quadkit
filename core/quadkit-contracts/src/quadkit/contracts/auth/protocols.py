"""Auth password and provider protocol class definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.core.provider import ProviderProtocol

if TYPE_CHECKING:
    from quadkit.contracts.auth.exceptions import AuthError
    from quadkit.contracts.auth.models import UserSession
    from quadkit.contracts.core.result import Result


@runtime_checkable
class LoginAttemptTrackerProtocol(Protocol):
    """Protocol for tracking failed login attempts and enforcing account lockout.

    Implementations must handle both in-process and distributed state (e.g.
    backed by a cache) so that multiple application instances share a
    consistent view of the failure window.
    """

    async def is_locked(self, identifier: str) -> bool:
        """Return ``True`` if *identifier* has exceeded the failure threshold.

        Args:
            identifier: Username, e-mail address, or IP used as the tracking key.

        Returns:
            ``True`` when the account is currently locked out, ``False`` otherwise.
        """
        ...

    async def record_failure(self, identifier: str) -> None:
        """Record a failed authentication attempt for *identifier*.

        Args:
            identifier: Username, e-mail address, or IP used as the tracking key.
        """
        ...

    async def clear(self, identifier: str) -> None:
        """Remove all recorded failures for *identifier* (call on successful login).

        Args:
            identifier: Username, e-mail address, or IP used as the tracking key.
        """
        ...


@runtime_checkable
class PasswordHasherProtocol(Protocol):
    """Protocol for password hashing services.

    Responsible for hashing passwords and verifying them against hashes.
    """

    async def hash(self, password: str) -> str:
        """Hash a plain text password.

        Args:
            password: Plain text password.

        Returns:
            Hashed password string.
        """
        ...

    async def verify(self, password: str, hashed_password: str) -> bool:
        """Verify a password against a hash.

        Args:
            password: Plain text password to check.
            hashed_password: Stored hash to compare against.

        Returns:
            True if password matches hash, False otherwise.
        """
        ...

    def needs_rehash(self, hashed_password: str) -> bool:
        """Return True when the stored hash should be re-computed.

        Implementations parse the cost parameters from the self-describing
        stored hash and compare them against their configured target.
        Unparseable or unknown formats return ``True`` (fail-closed) — safe
        because rehashing only ever runs after a successful ``verify()``.

        Args:
            hashed_password: Stored hash string.

        Returns:
            True when the hash is below the configured cost target.
        """
        ...

    async def rehash_if_needed(
        self,
        password: str,
        hashed_password: str | None,
    ) -> str | None:
        """Rehash *password* when *hashed_password* is below the cost target.

        Django ``check_password(setter=...)`` pattern: run this after a
        successful ``verify()`` and persist the returned hash to upgrade
        stored credentials in place.  Returns ``None`` when no upgrade is
        needed (or no stored hash exists).

        Args:
            password: Plain text password (already verified against the hash).
            hashed_password: Stored hash string, or None.

        Returns:
            A freshly computed hash when an upgrade is needed, else None.
        """
        ...


@runtime_checkable
class PasswordPolicyProtocol(Protocol):
    """Protocol for password policy enforcement.

    Validates that a plain-text password satisfies the application's
    complexity requirements (minimum length, character classes, etc.).
    """

    def validate(self, password: str) -> None:
        """Validate password against the policy.

        Args:
            password: Plain text password to validate.

        Raises:
            ValidationError: If the password violates the policy.
        """
        ...

    def is_valid(self, password: str) -> bool:
        """Return True if the password satisfies the policy without raising.

        Args:
            password: Plain text password.

        Returns:
            True if valid, False otherwise.
        """
        ...


@runtime_checkable
class MFAManagerProtocol(Protocol):
    """Protocol for multi-factor authentication lifecycle management."""

    async def enroll(self, user_id: str, method: str) -> dict[str, Any]: ...
    async def verify(self, user_id: str, method: str, code: str) -> bool: ...
    async def revoke(self, user_id: str, method: str) -> None: ...
    async def list_methods(self, user_id: str) -> list[str]: ...
    async def get_mfa(self, user_id: str) -> Any | None: ...


@runtime_checkable
class AuthSessionManagerProtocol(Protocol):
    """Protocol for managing device-aware, persistent login sessions.

    This is the auth-domain session manager: it tracks per-device browser/
    API sessions created on login (see :class:`~quadkit.contracts.auth.models.UserSession`).
    It is unrelated to ``quadkit.contracts.ai.session.SessionManagerProtocol``,
    which models multi-turn AI conversation state — the two must never be
    used interchangeably.
    """

    async def create_session(
        self,
        user_id: str,
        fingerprint_data: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
        expires_days: int = 30,
    ) -> UserSession:
        """Create a new login session for a user.

        Args:
            user_id: Unique identifier of the authenticating user.
            fingerprint_data: Raw device/browser fingerprint signals used to
                derive a stable ``device_id``.
            ip_address: Originating IP address, if known.
            user_agent: Originating User-Agent header, if known.
            expires_days: Session lifetime in days from creation.

        Returns:
            The newly created session.
        """
        ...

    async def validate_session(self, session_id: str) -> Result[UserSession, AuthError]:
        """Validate a session and refresh its last-active timestamp.

        Args:
            session_id: The session identifier to validate.

        Returns:
            ``Ok(session)`` if the session is valid and active, otherwise
            ``Err(AuthError)`` (not found, expired, or inactive).
        """
        ...

    async def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session.

        Args:
            session_id: The session to revoke.

        Returns:
            ``True`` when the revocation was processed.
        """
        ...

    async def verify_mfa(self, session_id: str) -> bool:
        """Mark a session as MFA-verified.

        Args:
            session_id: The session to mark as verified.

        Returns:
            ``True`` when the session was updated.
        """
        ...

    async def revoke_all_sessions(self, user_id: str) -> bool:
        """Revoke every active session belonging to a user.

        Args:
            user_id: The user whose sessions should be revoked.

        Returns:
            ``True`` when the revocation was processed.
        """
        ...

    async def get_active_sessions(self, user_id: str) -> list[UserSession]:
        """List all active sessions for a user.

        Args:
            user_id: The user to query.

        Returns:
            The user's currently active sessions.
        """
        ...


@runtime_checkable
class AuthProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for authentication and authorization providers.

    Auth providers are responsible for user authentication, authorization,
    token management, and access control.
    """

    # Optional managers — None when the feature is disabled/not configured
    user_store: Any | None
    session_manager: Any | None
    delegation_manager: Any | None
    api_key_manager: Any | None
    mfa_manager: MFAManagerProtocol | None

    async def get_user(self, user_id: str) -> Any | None:
        """Retrieve a user by their unique identifier.

        Args:
            user_id: Unique user identifier.

        Returns:
            User object or None if not found.
        """
        ...

    async def verify_token(self, token: str) -> Any:
        """Verify an encoded auth token and return verification details.

        Args:
            token: Raw encoded auth token (JWT or similar).

        Returns:
            Verification result (typically ``Result[VerifiedToken, TokenError]``).
        """
        ...

    def has_any_role(self, user: Any, roles: list[str]) -> bool:
        """Return True if *user* holds at least one of the given roles.

        Args:
            user: Authenticated user object.
            roles: Role names to check.

        Returns:
            True if the user has at least one of the supplied roles.
        """
        ...

    def has_any_permission(self, user: Any, permissions: list[str]) -> bool:
        """Return True if *user* has at least one of the given permissions.

        Args:
            user: Authenticated user object.
            permissions: Permission names to check.

        Returns:
            True if the user has at least one of the supplied permissions.
        """
        ...


__all__ = [
    "AuthProviderProtocol",
    "AuthSessionManagerProtocol",
    "LoginAttemptTrackerProtocol",
    "MFAManagerProtocol",
    "PasswordHasherProtocol",
    "PasswordPolicyProtocol",
]
