"""Session Management for Quadkit Auth."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from quadkit.auth.exceptions import (
    AuthenticationError,
    SessionNotFoundError,
    TokenExpiredError,
)
from quadkit.auth.models.session import UserSession
from quadkit.auth.session.fingerprint import generate_device_id
from quadkit.auth.storage.in_memory_stores import InMemorySessionStore
from quadkit.auth.storage.session_store import SessionStore
from quadkit.contracts.audit import AuditEntry, AuditLoggerProtocol
from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)

# Minimum seconds between last_active_at DB writes for the same session.
# Prevents an excessive write on every authenticated request under load.
_ACTIVITY_DEBOUNCE_SECONDS: float = 60.0


@inject
class SessionManagerImpl:
    """Manages persistent user sessions with device awareness.

    Uses SessionStore protocol for storage abstraction, allowing different
    backends (SQL, Redis, in-memory).
    """

    DEFAULT_EXPIRY_DAYS = 30

    def __init__(
        self,
        session_store: SessionStore | None = None,
        ids: IdGeneratorProtocol | None = None,
        *,
        audit_logger: AuditLoggerProtocol | None = None,
        revoke_token: Callable[[str], Awaitable[None]] | None = None,
        max_sessions_per_user: int | None = None,
    ) -> None:
        """Initialise the session manager.

        Args:
            session_store: Optional storage backend.  Defaults to an
                :class:`~quadkit.auth.storage.in_memory_stores.InMemorySessionStore`
                when not provided.
            audit_logger: Optional :class:`~quadkit.contracts.audit.AuditLoggerProtocol`
                used to record security-sensitive session events (create /
                revoke).  No audit entries are written when *None*.
            revoke_token: Optional async callable that accepts a JTI string and
                adds it to the token blacklist.  When provided, revoking a
                session also invalidates its associated JWT access token.
            max_sessions_per_user: Maximum concurrent sessions per user before
                the least-recently-used session is evicted.  ``None`` (the
                default) means no limit is enforced.
        """
        self._store: SessionStore = session_store or InMemorySessionStore()
        self._ids = ids
        self._audit_logger: AuditLoggerProtocol | None = audit_logger
        self._revoke_token: Callable[[str], Awaitable[None]] | None = revoke_token
        self._max_sessions_per_user: int | None = max_sessions_per_user
        # Tracks the last monotonic timestamp at which last_active_at was written
        # for each session, so that we can debounce the per-request DB write.
        self._last_activity_write: dict[str, float] = {}

    def __repr__(self) -> str:
        """Return developer-friendly string representation."""
        return f"SessionManagerImpl(store={self._store!r})"

    @property
    def store(self) -> SessionStore:
        """The storage backend currently in use."""
        return self._store

    def use_store(self, store: SessionStore) -> None:
        """Rebind the backing store.

        For host applications whose storage provider registers *after* the
        auth bundle: the manager is a singleton built during the bundle's
        boot, so by the time an application can offer a SQL session store
        the manager already exists and is holding the in-memory default.
        Without this the application silently keeps the default — sessions
        that vanish on restart and are invisible to a second worker, which
        is the one failure mode a session list must not have.

        Call before the manager is used; existing in-memory sessions are
        not migrated.
        """
        self._store = store
        self._last_activity_write.clear()

    async def create_session(
        self,
        user_id: str,
        fingerprint_data: dict[str, Any],
        ip_address: str | None = None,
        user_agent: str | None = None,
        expires_days: int = DEFAULT_EXPIRY_DAYS,
    ) -> UserSession:
        """Create a new session for a user."""
        device_id = generate_device_id(fingerprint_data)

        active_sessions = await self.get_active_sessions(user_id)
        if (
            self._max_sessions_per_user is not None
            and len(active_sessions) >= self._max_sessions_per_user
        ):
            sorted_sessions = sorted(
                active_sessions,
                key=lambda s: s.last_active_at or s.created_at or datetime.min,
            )
            await self.revoke_session(sorted_sessions[0].session_id)
            logger.info("Revoked oldest session for user %s due to limit", user_id)

        session_id = (
            self._ids.generate_for("Session")
            if self._ids
            else self._generate_fallback_id()
        )
        now = ambient_clock.now()
        expires_at = now + timedelta(days=expires_days)

        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            user_agent=user_agent,
            fingerprint=fingerprint_data,
            expires_at=expires_at,
            created_at=now,
            last_active_at=now,
        )

        await self._store.create(session)

        logger.info(
            "Created session %s for user %s (Device: %s)",
            session_id,
            user_id,
            device_id,
        )

        if self._audit_logger is not None:
            await self._audit_logger.log(
                AuditEntry(
                    action="session.created",
                    actor_id=user_id,
                    resource_type="Session",
                    resource_id=session_id,
                    outcome="success",
                    metadata={
                        "device_id": device_id,
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                    },
                )
            )

        return session

    async def validate_session(
        self, session_id: str
    ) -> Result[
        UserSession, AuthenticationError | SessionNotFoundError | TokenExpiredError
    ]:
        """Validate a session and update its activity.

        Args:
            session_id: The session identifier to validate.

        Returns:
            Ok(session) if the session is valid and active.
            Err(SessionNotFoundError) if the session does not exist.
            Err(TokenExpiredError) if the session has expired (it is also revoked).
            Err(AuthenticationError) if the session exists but is inactive.
        """
        session = await self._store.get(session_id)

        if not session:
            return Err(SessionNotFoundError(session_id))

        if session.is_expired():
            await self.revoke_session(session_id)
            logger.warning("Session %s expired", session_id)
            return Err(TokenExpiredError("Session has expired"))

        if not session.is_active:
            return Err(AuthenticationError("Session is inactive"))

        now = ambient_clock.monotonic()
        last_write = self._last_activity_write.get(session_id, 0.0)
        if now - last_write >= _ACTIVITY_DEBOUNCE_SECONDS:
            wall_now = ambient_clock.now()
            await self._store.update(
                session_id,
                last_active_at=wall_now,
            )
            self._last_activity_write[session_id] = now
            self._prune_activity_write_cache(now)

        return Ok(session)

    def _prune_activity_write_cache(self, now: float) -> None:
        """Remove stale entries from the activity-write tracker.

        Entries older than 2x the debounce window can never influence a future
        debounce decision, so they are safe to discard.  Pruning on every write
        (rather than on a timer) keeps memory bounded without background threads.
        """
        cutoff = now - (_ACTIVITY_DEBOUNCE_SECONDS * 2)
        stale = [sid for sid, ts in self._last_activity_write.items() if ts < cutoff]
        for sid in stale:
            del self._last_activity_write[sid]

    async def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session.

        If a ``revoke_token`` callback was provided at construction time and
        the session has an associated ``token_jti``, the JWT is added to the
        token blacklist so it cannot be reused until natural expiry.
        """
        # Fetch the session before revoking so we can include user_id in audit log
        # and blacklist its associated JWT if a token-revocation callback is set.
        needs_fetch = self._audit_logger is not None or self._revoke_token is not None
        session = await self._store.get(session_id) if needs_fetch else None

        await self._store.update(
            session_id,
            is_active=False,
            updated_at=ambient_clock.now(),
        )
        logger.info("Revoked session: %s", session_id)

        # Blacklist the associated JWT access token if we have a JTI and callback
        if session and session.token_jti and self._revoke_token is not None:
            try:
                await self._revoke_token(session.token_jti)
                logger.debug(
                    "Blacklisted JWT jti=%s on session revocation", session.token_jti
                )
            except Exception as e:  # noqa: BLE001 — token blacklisting is best-effort; session revocation must continue
                logger.warning(
                    "Failed to blacklist token jti=%s during session revocation: %s",
                    session.token_jti,
                    e,
                )

        if self._audit_logger is not None:
            actor = session.user_id if session else session_id
            await self._audit_logger.log(
                AuditEntry(
                    action="session.revoked",
                    actor_id=actor,
                    resource_type="Session",
                    resource_id=session_id,
                    outcome="success",
                )
            )

        return True

    async def verify_mfa(self, session_id: str) -> bool:
        """Mark the session as MFA verified."""
        now = ambient_clock.now()
        await self._store.update(
            session_id,
            mfa_verified_at=now,
            updated_at=now,
        )
        logger.info("MFA verified for session: %s", session_id)
        return True

    async def revoke_all_sessions(self, user_id: str) -> bool:
        """Revoke all active sessions for a user."""
        await self._store.delete_all_for_user(user_id)
        logger.info("Revoked all sessions for user: %s", user_id)
        return True

    async def get_active_sessions(self, user_id: str) -> list[UserSession]:
        """List all active sessions for a user."""
        return await self._store.list_for_user(user_id)

    def _generate_fallback_id(self) -> str:
        """Generate session ID when IdGenerator is not injected."""
        import uuid as uuid_module

        return str(uuid_module.uuid4())


__all__ = [
    "SessionManagerImpl",
    "logger",
]
