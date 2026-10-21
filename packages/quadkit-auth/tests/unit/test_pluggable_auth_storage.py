"""Storage seams a host application has to be able to fill.

Three defaults in this package are correct for a library and wrong for a
deployment: sessions in a dict, a staged MFA enrolment in a dict, and a
password-reset lookup that scans the first 1000 users. Each one now has a
way for an application to supply its own storage. These tests pin the
seams, because a seam that silently falls back to the default is worse
than no seam at all — the application believes it is persistent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pyotp
import pytest

from quadkit.auth.authn.password_reset import PasswordResetService
from quadkit.auth.di.sub_providers.session_provider import SessionProvider
from quadkit.auth.mfa.manager import MFAManager
from quadkit.auth.models.session import UserSession
from quadkit.auth.models.user import User, UserCredentials
from quadkit.auth.session.manager import SessionManagerImpl
from quadkit.auth.storage.in_memory_stores import InMemorySessionStore


class _RecordingSessionStore(InMemorySessionStore):
    """An in-memory store that can be told apart from the default one."""


class _Container:
    """The smallest registrar/resolver the providers actually use."""

    def __init__(self, bindings: dict[Any, Any] | None = None) -> None:
        self.singletons: dict[Any, Any] = {}
        self._bindings = bindings or {}

    def singleton(self, key: Any, value: Any = None, factory: Any = None) -> None:
        self.singletons[key] = factory if factory is not None else value

    async def resolve_optional(self, key: Any) -> Any:
        return self._bindings.get(key)


class _MemoryUserStore:
    """Enough of ``UserStoreProtocol`` for the flows under test."""

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.credentials: dict[str, UserCredentials] = {}
        self.reset_lookups: list[str] = []

    def add(self, user: User) -> User:
        self.users[user.user_id] = user
        return user

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    async def update_user(self, user: User) -> None:
        self.users[user.user_id] = user

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        raise AssertionError(
            "the scan fallback must not run when the store can look up"
        )

    async def update_credentials(self, creds: UserCredentials) -> None:
        self.credentials[creds.user_id] = creds


class _ResetAwareUserStore(_MemoryUserStore):
    async def get_user_by_reset_token(self, token: str) -> User | None:
        self.reset_lookups.append(token)
        return next(
            (
                user
                for user in self.users.values()
                if getattr(user, "password_reset_token", None) == token
            ),
            None,
        )


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_provider_uses_a_bound_store() -> None:
    """A registered SessionStore is what the manager ends up holding."""
    from quadkit.auth.storage.session_store import SessionStore

    store = _RecordingSessionStore()
    container = _Container({SessionStore: store})
    await SessionProvider().register(container)

    factory = container.singletons[SessionManagerImpl]
    manager = await factory(container)
    assert manager.store is store


@pytest.mark.asyncio
async def test_session_provider_falls_back_and_shares_one_manager() -> None:
    """No binding means in-memory, and both bindings resolve the same object."""
    from quadkit.contracts.auth.protocols import AuthSessionManagerProtocol

    container = _Container()
    await SessionProvider().register(container)

    manager = await container.singletons[SessionManagerImpl](container)
    via_protocol = await container.singletons[AuthSessionManagerProtocol](container)
    assert isinstance(manager.store, InMemorySessionStore)
    # Two managers would mean a session created through one is invisible
    # to the other — the kind of split nobody notices until logout.
    assert via_protocol is manager


@pytest.mark.asyncio
async def test_use_store_rebinds_a_manager_that_already_exists() -> None:
    """For applications whose storage provider registers after the bundle."""
    manager = SessionManagerImpl()
    assert isinstance(manager.store, InMemorySessionStore)

    store = _RecordingSessionStore()
    await store.create(
        UserSession(
            session_id="s-1",
            user_id="u-1",
            device_id="d-1",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    manager.use_store(store)

    assert manager.store is store
    assert [s.session_id for s in await manager.get_active_sessions("u-1")] == ["s-1"]


# ---------------------------------------------------------------------------
# password reset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_prefers_the_store_lookup_over_scanning_users() -> None:
    """The scan caps at 1000 users and cannot match a digested token."""
    store = _ResetAwareUserStore()
    store.add(User(user_id="u-1", email="operator@example.test", name="Operator"))
    service = PasswordResetService(user_store=store)

    issued = await service.request_reset("operator@example.test")
    token, _expiry = issued.unwrap()

    # `_MemoryUserStore.list_users` raises, so a passing confirm proves the
    # hook was used rather than the fallback.
    confirmed = await service.confirm_reset(token, "FreshHorse11")
    assert not confirmed.is_err()
    assert store.reset_lookups == [token]
    assert store.credentials["u-1"].hashed_password


@pytest.mark.asyncio
async def test_reset_rejects_a_token_the_store_does_not_know() -> None:
    store = _ResetAwareUserStore()
    store.add(User(user_id="u-1", email="operator@example.test", name="Operator"))
    service = PasswordResetService(user_store=store)

    result = await service.confirm_reset("not-the-token", "FreshHorse11")
    assert result.is_err()


# ---------------------------------------------------------------------------
# staged MFA enrolment
# ---------------------------------------------------------------------------


class _PendingStore:
    def __init__(self) -> None:
        self.saved: dict[str, dict[str, Any]] = {}
        self.pops: list[str] = []

    async def save(self, token: str, payload: dict[str, Any], expires_at: int) -> None:
        self.saved[token] = {**payload, "expires_at": expires_at}

    async def pop(self, token: str) -> dict[str, Any] | None:
        self.pops.append(token)
        return self.saved.pop(token, None)


@pytest.mark.asyncio
async def test_enrolment_staging_goes_through_a_supplied_store() -> None:
    """So a browser can start on one worker and finish on another."""
    users = _MemoryUserStore()
    users.add(User(user_id="u-1", email="operator@example.test", name="Operator"))
    pending = _PendingStore()
    manager = MFAManager(user_store=users, pending_store=pending)

    staged = await manager.begin_totp_setup("u-1")
    assert list(pending.saved) == [staged["setup_token"]]
    assert manager._pending_setups == {}

    codes = await manager.complete_totp_setup(
        "u-1",
        staged["setup_token"],
        pyotp.TOTP(staged["secret"]).now(),
    )
    assert codes
    assert pending.pops == [staged["setup_token"]]
    assert users.users["u-1"].profile["mfa"]["enabled"] is True


@pytest.mark.asyncio
async def test_a_staged_enrolment_is_spent_even_when_the_code_is_wrong() -> None:
    """Otherwise the window is a guessing window."""
    users = _MemoryUserStore()
    users.add(User(user_id="u-1", email="operator@example.test", name="Operator"))
    pending = _PendingStore()
    manager = MFAManager(user_store=users, pending_store=pending)

    staged = await manager.begin_totp_setup("u-1")
    assert (
        await manager.complete_totp_setup("u-1", staged["setup_token"], "000000")
        is None
    )
    assert pending.saved == {}
    assert (
        await manager.complete_totp_setup("u-1", staged["setup_token"], "000000")
        is None
    )


@pytest.mark.asyncio
async def test_the_in_process_default_still_works() -> None:
    """The seam must not change behaviour for callers that ignore it."""
    users = _MemoryUserStore()
    users.add(User(user_id="u-1", email="operator@example.test", name="Operator"))
    manager = MFAManager(user_store=users)

    staged = await manager.begin_totp_setup("u-1")
    assert staged["setup_token"] in manager._pending_setups
    codes = await manager.complete_totp_setup(
        "u-1",
        staged["setup_token"],
        pyotp.TOTP(staged["secret"]).now(),
    )
    assert codes
