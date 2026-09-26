"""Tests for PasswordResetService."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pytest

from quadkit.auth.authn.password_reset import (
    PasswordResetService,
    PasswordResetTokenError,
)


@dataclass
class _User:
    user_id: str = "u1"
    email: str = "a@b.c"
    password_reset_token: str | None = None
    password_reset_expires_at: datetime | None = None


class _FakeStore:
    def __init__(self, users: list[_User] | None = None, fail: bool = False) -> None:
        self.users = users or []
        self.fail = fail
        self.updated: list[Any] = []
        self.credentials: list[Any] = []

    async def get_user_by_email(self, email: str) -> _User | None:
        if self.fail:
            raise RuntimeError("store boom")
        return next((u for u in self.users if u.email == email), None)

    async def get_user_by_id(self, user_id: str) -> _User | None:
        if self.fail:
            raise RuntimeError("store boom")
        return next((u for u in self.users if u.user_id == user_id), None)

    async def update_user(self, user: Any) -> None:
        self.updated.append(user)

    async def update_credentials(self, creds: Any) -> None:
        self.credentials.append(creds)

    async def list_users(self, skip: int = 0, limit: int = 100) -> list[_User]:
        return self.users[skip : skip + limit]


@pytest.fixture
def service() -> PasswordResetService:
    return PasswordResetService(_FakeStore())


class TestGenerateResetToken:
    def test_returns_token_and_expiry(self, service: PasswordResetService) -> None:
        token, expiry = service.generate_reset_token()
        assert isinstance(token, str)
        assert len(token) >= 40  # urlsafe(32 bytes) -> 43 chars
        assert isinstance(expiry, datetime)
        # default TTL is 24h
        from quadkit.primitives import clock

        delta = expiry - clock.now()
        assert timedelta(hours=23) < delta <= timedelta(hours=24)

    def test_custom_ttl(self) -> None:
        from quadkit.primitives import clock

        svc = PasswordResetService(_FakeStore(), token_ttl_hours=1)
        _, expiry = svc.generate_reset_token()
        delta = expiry - clock.now()
        assert timedelta(hours=0, minutes=59) < delta <= timedelta(hours=1)

    def test_tokens_unique(self, service: PasswordResetService) -> None:
        t1, _ = service.generate_reset_token()
        t2, _ = service.generate_reset_token()
        assert t1 != t2


class TestRequestReset:
    @pytest.mark.asyncio
    async def test_nonexistent_email_returns_ok_none(self) -> None:
        svc = PasswordResetService(_FakeStore([]))
        result = await svc.request_reset("ghost@example.com")
        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_existing_user_returns_token_pair(self) -> None:
        store = _FakeStore([_User(email="a@b.c")])
        svc = PasswordResetService(store)
        result = await svc.request_reset("a@b.c")
        assert result.is_ok()
        token, expiry = result.unwrap()
        assert token
        assert isinstance(expiry, datetime)
        assert len(store.updated) == 1

    @pytest.mark.asyncio
    async def test_repr(self) -> None:
        svc = PasswordResetService(_FakeStore())
        assert "_FakeStore" in repr(svc)


class TestConfirmReset:
    @pytest.mark.asyncio
    async def test_invalid_token_returns_err(self) -> None:
        svc = PasswordResetService(_FakeStore([_User()]))
        result = await svc.confirm_reset("wrong-token", "newpass")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), PasswordResetTokenError)

    @pytest.mark.asyncio
    async def test_expired_token_returns_err(self) -> None:
        from quadkit.primitives import clock

        user = _User(
            password_reset_token="tok",
            password_reset_expires_at=clock.now() - timedelta(hours=1),
        )
        svc = PasswordResetService(_FakeStore([user]))
        result = await svc.confirm_reset("tok", "newpass")
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_valid_token_updates_credentials(self) -> None:
        from quadkit.primitives import clock

        user = _User(
            password_reset_token="tok",
            password_reset_expires_at=clock.now() + timedelta(hours=1),
        )
        store = _FakeStore([user])
        svc = PasswordResetService(store)
        result = await svc.confirm_reset("tok", "newpass")
        assert result.is_ok()
        assert len(store.credentials) == 1
        creds = store.credentials[0]
        assert creds.user_id == "u1"
        assert creds.hashed_password  # bcrypt hash string

    @pytest.mark.asyncio
    async def test_user_without_token_attribute_skipped(self) -> None:
        class _BareUser:
            user_id = "u9"

        svc = PasswordResetService(_FakeStore([_BareUser()]))  # type: ignore[arg-type]
        result = await svc.confirm_reset("tok", "newpass")
        assert result.is_err()


class TestInvalidateToken:
    @pytest.mark.asyncio
    async def test_clears_pending_token(self) -> None:
        user = _User(password_reset_token="tok", password_reset_expires_at=None)
        store = _FakeStore([user])
        svc = PasswordResetService(store)
        await svc.invalidate_token("u1")
        assert user.password_reset_token is None
        assert len(store.updated) == 1

    @pytest.mark.asyncio
    async def test_missing_user_noop(self) -> None:
        store = _FakeStore([])
        svc = PasswordResetService(store)
        await svc.invalidate_token("ghost")
        assert store.updated == []


class TestErrorType:
    def test_code(self) -> None:
        assert PasswordResetTokenError._code == "QK_ERR_AUTH_028"


class _CopyingStore(_FakeStore):
    """A store that snapshots rows on update (ORM/DB semantics).

    Regression harness for the persistence bug: `request_reset` used to
    call `update_user(user)` BEFORE attaching the generated token, so any
    store that materializes rows at update time never saw the token and
    `confirm_reset` could never match — dead flow on real storage.
    """

    def __init__(self, users: list[_User] | None = None) -> None:
        super().__init__(users)
        self.rows: dict[str, dict[str, Any]] = {}

    def _snapshot(self, user: Any) -> None:
        self.rows[user.user_id] = {
            "password_reset_token": getattr(user, "password_reset_token", None),
            "password_reset_expires_at": getattr(user, "password_reset_expires_at", None),
        }

    async def update_user(self, user: Any) -> None:
        await super().update_user(user)
        self._snapshot(user)

    async def get_user_by_email(self, email: str) -> _User | None:
        for user in self.users:
            if user.email == email:
                stored = self.rows.get(user.user_id, {})
                user.password_reset_token = stored.get("password_reset_token")
                user.password_reset_expires_at = stored.get("password_reset_expires_at")
                return user
        return None


@pytest.mark.asyncio
async def test_request_reset_persists_token_on_updating_stores() -> None:
    """The token must be ON the user when update_user runs (GWA-38)."""

    user = _User()
    store = _CopyingStore([user])
    svc = PasswordResetService(store)

    result = await svc.request_reset("a@b.c")
    assert result.is_ok()
    token, _ = result.unwrap()
    stored = store.rows[user.user_id]
    assert stored["password_reset_token"] == token
    assert stored["password_reset_expires_at"] is not None

    # And confirm_reset can actually find it on the copied row.
    confirmed = await svc.confirm_reset(token, "new-password-123")
    assert confirmed.is_ok()
    assert store.credentials
    assert store.credentials[0].user_id == "u1"


@pytest.mark.asyncio
async def test_confirm_reset_clears_token_single_use() -> None:
    """A used token must not confirm twice within its TTL."""
    user = _User()
    store = _CopyingStore([user])
    svc = PasswordResetService(store)

    token, _ = (await svc.request_reset("a@b.c")).unwrap()
    assert (await svc.confirm_reset(token, "first-password-1")).is_ok()
    replay = await svc.confirm_reset(token, "second-password")
    assert replay.is_err()
