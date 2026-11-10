"""Explicit encrypted SQLite session persistence through the database contract.

No schema creation, key generation, cookie routes or silent in-memory fallback.
The host owns migrations and a stable Fernet key separate from its JWT key.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
import hashlib
from typing import TYPE_CHECKING, Any

from cryptography.fernet import Fernet, InvalidToken

from quadkit import serialization
from quadkit.auth.models.session import UserSession
from quadkit.primitives import clock

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol

SQLITE_SESSION_SCHEMA = """CREATE TABLE auth_sessions (
    session_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at REAL NOT NULL,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    payload TEXT NOT NULL
)"""
SQLITE_SESSION_INDEX = (
    "CREATE INDEX auth_sessions_user ON auth_sessions(user_id, is_active, expires_at)"
)
_DATES = frozenset(
    {"expires_at", "last_active_at", "mfa_verified_at", "created_at", "updated_at"}
)
_MUTABLE = frozenset(
    {"last_active_at", "mfa_verified_at", "updated_at", "expires_at", "is_active"}
)


class SQLSessionStore:
    """Encrypted session records with atomic, non-resurrecting updates.

    Supports SQLite parameter syntax. Hosts explicitly apply the exported schema
    and index using their migration system. No portability claim to other SQL
    engines. Revocation retains a tombstone, preventing session-ID reuse. No
    automatic deletion: hosts must define retention before purging tombstones.
    User IDs and expiry/activity indexes are plaintext; session IDs, device/IP
    metadata and associated JWT identifiers are authenticated-encrypted at rest.
    """

    def __init__(self, db: DatabaseProviderProtocol, *, encryption_key: bytes) -> None:
        self._db = db
        self._cipher = Fernet(encryption_key)

    @staticmethod
    def _hash(session_id: str) -> str:
        if not isinstance(session_id, str) or not session_id or len(session_id) > 512:
            raise ValueError("Invalid session identifier")
        return hashlib.sha256(session_id.encode()).hexdigest()

    @staticmethod
    def _expiry(value: object) -> float:
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError("Persistent sessions require a timezone-aware expiration")
        return value.timestamp()

    def _encode(self, session: UserSession) -> str:
        self._hash(session.session_id)
        if (
            not isinstance(session.user_id, str)
            or not session.user_id
            or len(session.user_id) > 512
        ):
            raise ValueError("Invalid session owner")
        self._expiry(session.expires_at)
        if type(session.is_active) is not bool:
            raise ValueError("Session activity must be boolean")
        values = asdict(session)
        for name in _DATES:
            value = values[name]
            if value is not None:
                self._expiry(value)
                values[name] = value.astimezone(UTC).isoformat()
        raw = serialization.dumps_str(values).encode()
        if len(raw) > 65536:
            raise ValueError("Session metadata exceeds 64 KiB")
        return self._cipher.encrypt(raw).decode("ascii")

    def _decode(self, row: dict[str, Any]) -> UserSession:
        try:
            raw = self._cipher.decrypt(row["payload"].encode("ascii"))
            values = serialization.loads(raw)
            for name in _DATES:
                if values[name] is not None:
                    values[name] = datetime.fromisoformat(values[name])
            session = UserSession(**values)
            if (
                self._hash(session.session_id) != row["session_hash"]
                or session.user_id != row["user_id"]
                or self._expiry(session.expires_at) != row["expires_at"]
            ):
                raise ValueError("Session indexes do not match encrypted record")
            # Revocations deliberately need not decrypt/re-encrypt the payload.
            return replace(session, is_active=bool(row["is_active"]))
        except (InvalidToken, ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise RuntimeError("Session record cannot be authenticated") from exc

    async def create(self, session: UserSession) -> str:
        """Insert only; a duplicate or previously revoked ID is never replaced."""
        encoded = self._encode(session)
        if (
            not session.is_active
            or self._expiry(session.expires_at) <= clock.timestamp()
        ):
            raise ValueError("Cannot create an inactive or expired session")
        result = await self._db.execute(
            "INSERT INTO auth_sessions(session_hash, user_id, expires_at, is_active, payload) VALUES (?, ?, ?, 1, ?)",
            [
                self._hash(session.session_id),
                session.user_id,
                self._expiry(session.expires_at),
                encoded,
            ],
        )
        if not result.success or result.row_count != 1:
            raise RuntimeError("Session persistence failed")
        return session.session_id

    async def get(self, session_id: str) -> UserSession | None:
        """Read through storage on every call; unavailable storage raises."""
        result = await self._db.execute_query(
            "SELECT * FROM auth_sessions WHERE session_hash = ? AND is_active = 1 AND expires_at > ?",
            [self._hash(session_id), clock.timestamp()],
        )
        if not result.success:
            raise RuntimeError("Session lookup failed")
        return self._decode(result.rows[0]) if result.rows else None

    async def update(self, session_id: str, **updates: object) -> None:
        """CAS-update mutable fields; revocation/expiry cannot be undone by a stale writer."""
        if set(updates) - _MUTABLE:
            raise ValueError("Session identity and device metadata are immutable")
        if "is_active" in updates:
            if updates["is_active"] is not False:
                raise ValueError("Session reactivation is forbidden")
            await self.delete(session_id)
            return
        for name, value in updates.items():
            if name in _DATES:
                self._expiry(value)
        key = self._hash(session_id)
        for _ in range(8):
            result = await self._db.execute_query(
                "SELECT * FROM auth_sessions WHERE session_hash = ? AND is_active = 1 AND expires_at > ?",
                [key, clock.timestamp()],
            )
            if not result.success:
                raise RuntimeError("Session update lookup failed")
            if not result.rows:
                return
            row = result.rows[0]
            current = self._decode(row)
            validated: dict[str, Any] = dict(updates)
            updated = replace(current, **validated)
            encoded = self._encode(updated)
            changed = await self._db.execute(
                "UPDATE auth_sessions SET payload = ?, expires_at = ? WHERE session_hash = ? "
                "AND payload = ? AND is_active = 1 AND expires_at > ?",
                [
                    encoded,
                    self._expiry(updated.expires_at),
                    key,
                    row["payload"],
                    clock.timestamp(),
                ],
            )
            if not changed.success:
                raise RuntimeError("Session update failed")
            if changed.row_count == 1:
                return
        raise RuntimeError("Session update contention limit exceeded")

    async def delete(self, session_id: str) -> bool:
        """Revoke once, retaining the ID tombstone to prevent replay via recreation."""
        result = await self._db.execute(
            "UPDATE auth_sessions SET is_active = 0 WHERE session_hash = ? AND is_active = 1",
            [self._hash(session_id)],
        )
        if not result.success:
            raise RuntimeError("Session revocation failed")
        return result.row_count == 1

    async def delete_all_for_user(self, user_id: str) -> int:
        """Revoke existing sessions in one statement; future logins are not blocked."""
        result = await self._db.execute(
            "UPDATE auth_sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
            [user_id],
        )
        if not result.success:
            raise RuntimeError("User session revocation failed")
        return result.row_count

    async def list_for_user(self, user_id: str) -> list[UserSession]:
        """Return active unexpired sessions, authenticating each encrypted record."""
        result = await self._db.execute_query(
            "SELECT * FROM auth_sessions WHERE user_id = ? AND is_active = 1 AND expires_at > ?",
            [user_id, clock.timestamp()],
        )
        if not result.success:
            raise RuntimeError("Session listing failed")
        return [self._decode(row) for row in result.rows]
