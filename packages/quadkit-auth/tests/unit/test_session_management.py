from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from quadkit.auth.exceptions import (
    AuthenticationError,
    SessionNotFoundError,
    TokenExpiredError,
)
from quadkit.auth.models.session import UserSession
from quadkit.auth.session.fingerprint import generate_device_id
from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.auth.storage.in_memory_stores import InMemorySessionStore


def test_generate_device_id():
    d1 = {"ua": "Mozilla", "res": "1920x1080"}
    d2 = {"res": "1920x1080", "ua": "Mozilla"}
    d3 = {"ua": "Chrome"}

    id1 = generate_device_id(d1)
    id2 = generate_device_id(d2)
    id3 = generate_device_id(d3)

    assert id1 == id2
    assert id1 != id3
    assert len(id1) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_session_manager_create():
    store = InMemorySessionStore()
    manager = SessionManagerImpl(session_store=store)

    fingerprint = {"ua": "test"}
    session = await manager.create_session("user-123", fingerprint)

    assert session.user_id == "user-123"
    assert session.device_id == generate_device_id(fingerprint)


@pytest.mark.asyncio
async def test_session_manager_limit():
    store = InMemorySessionStore()
    manager = SessionManagerImpl(session_store=store, max_sessions_per_user=2)

    existing_sessions = [
        UserSession(
            session_id="s1",
            user_id="u1",
            device_id="d1",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
        ),
        UserSession(
            session_id="s2",
            user_id="u1",
            device_id="d2",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC),
            last_active_at=datetime.now(UTC),
        ),
    ]

    for session in existing_sessions:
        await store.create(session)

    await manager.create_session("u1", {"ua": "new"})

    sessions = await store.list_for_user("u1")
    assert len(sessions) <= 2


class TestValidateSessionResult:
    """SessionManagerImpl.validate_session returns Result[UserSession, AuthError]."""

    @pytest.mark.asyncio
    async def test_validate_session_returns_ok_for_valid_session(self) -> None:
        """validate_session returns Ok(session) for an active, non-expired session."""
        store = InMemorySessionStore()
        manager = SessionManagerImpl(session_store=store)
        session = await manager.create_session("user-1", {"ua": "test"})

        result = await manager.validate_session(session.session_id)

        assert result.is_ok()
        assert result.unwrap().session_id == session.session_id

    @pytest.mark.asyncio
    async def test_validate_session_returns_err_session_not_found(self) -> None:
        """validate_session returns Err(SessionNotFoundError) for unknown session IDs."""
        store = InMemorySessionStore()
        manager = SessionManagerImpl(session_store=store)

        result = await manager.validate_session("nonexistent-id")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), SessionNotFoundError)

    @pytest.mark.asyncio
    async def test_validate_session_returns_err_token_expired(self) -> None:
        """validate_session returns Err(TokenExpiredError) for an expired session."""
        store = InMemorySessionStore()
        manager = SessionManagerImpl(session_store=store)

        # Create a session that is already expired.
        expired_session = UserSession(
            session_id="expired-session",
            user_id="user-2",
            device_id="dev-1",
            created_at=datetime.now(UTC) - timedelta(days=60),
            expires_at=datetime.now(UTC) - timedelta(days=30),
            last_active_at=datetime.now(UTC) - timedelta(days=30),
        )
        await store.create(expired_session)

        result = await manager.validate_session("expired-session")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), TokenExpiredError)

    @pytest.mark.asyncio
    async def test_validate_session_returns_err_authentication_error_for_inactive(
        self,
    ) -> None:
        """validate_session returns Err(AuthenticationError) for an inactive session."""
        store = InMemorySessionStore()
        manager = SessionManagerImpl(session_store=store)

        inactive_session = UserSession(
            session_id="inactive-session",
            user_id="user-3",
            device_id="dev-2",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=30),
            last_active_at=datetime.now(UTC),
            is_active=False,
        )
        await store.create(inactive_session)

        result = await manager.validate_session("inactive-session")

        assert result.is_err()
        assert isinstance(result.unwrap_err(), AuthenticationError)


class TestSessionActivityDebounce:
    """P2-session-write: last_active_at DB write must be debounced."""

    @pytest.mark.asyncio
    async def test_session_activity_write_is_debounced(self) -> None:
        """P2: last_active_at DB write must be skipped if called within debounce window."""
        store = InMemorySessionStore()
        store.update = AsyncMock(wraps=store.update)

        manager = SessionManagerImpl(session_store=store)
        session = await manager.create_session("user-debounce", {"ua": "test"})

        # Reset the mock call count after create_session (which doesn't call update)
        store.update.reset_mock()

        # Call validate_session twice in rapid succession (well within debounce window)
        result1 = await manager.validate_session(session.session_id)
        result2 = await manager.validate_session(session.session_id)

        assert result1.is_ok()
        assert result2.is_ok()

        # The DB write should have been issued only once — the second call is debounced
        update_calls_with_activity = [
            call
            for call in store.update.call_args_list
            if "last_active_at" in call.kwargs
        ]
        assert len(update_calls_with_activity) == 1, (
            f"Expected 1 last_active_at write within debounce window, "
            f"got {len(update_calls_with_activity)}"
        )

    @pytest.mark.asyncio
    async def test_session_activity_write_fires_after_debounce_window(self) -> None:
        """P2: last_active_at DB write must fire again after the debounce window expires."""
        import time

        store = InMemorySessionStore()
        store.update = AsyncMock(wraps=store.update)

        manager = SessionManagerImpl(session_store=store)
        session = await manager.create_session("user-debounce-2", {"ua": "test"})
        store.update.reset_mock()

        # First call — write should happen
        result1 = await manager.validate_session(session.session_id)
        assert result1.is_ok()

        # Simulate time passing beyond the debounce window by manipulating the tracker
        session_id = session.session_id
        manager._last_activity_write[session_id] = time.monotonic() - 120.0

        # Second call — debounce window has expired, write should happen again
        result2 = await manager.validate_session(session.session_id)
        assert result2.is_ok()

        update_calls_with_activity = [
            call
            for call in store.update.call_args_list
            if "last_active_at" in call.kwargs
        ]
        assert len(update_calls_with_activity) == 2, (
            f"Expected 2 last_active_at writes (one per debounce window), "
            f"got {len(update_calls_with_activity)}"
        )

    @pytest.mark.asyncio
    async def test_last_activity_write_dict_is_pruned(self) -> None:
        """P2: Stale entries older than 2× debounce window must be removed to prevent unbounded growth."""
        import time

        store = InMemorySessionStore()
        manager = SessionManagerImpl(session_store=store)

        # Seed the dict with stale entries (> 2x debounce window old)
        manager._last_activity_write["stale-session-1"] = time.monotonic() - 200.0
        manager._last_activity_write["stale-session-2"] = time.monotonic() - 200.0

        # Create and validate a real session to trigger a write (and the pruning pass)
        session = await manager.create_session("user-prune", {"ua": "test"})
        await manager.validate_session(session.session_id)

        # Stale entries must have been pruned
        assert "stale-session-1" not in manager._last_activity_write
        assert "stale-session-2" not in manager._last_activity_write
