"""The login flow must hash/verify through the injected hasher (F3)."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydantic import SecretStr
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.password_hasher import (
    Argon2idKeyDerivation,
    Argon2idPasswordHasher,
    ComposedPasswordHasher,
)
from quadkit.auth.authn.schemas import RegisterRequest
from quadkit.auth.authn.security import PasswordHasher
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.contracts.auth import PasswordHasherProtocol


class _SpyHasher:
    """Records hash/verify calls, delegating to a real bcrypt hasher."""

    def __init__(self) -> None:
        self.hash_calls: list[str] = []
        self.verify_calls: list[str] = []
        self._real = PasswordHasher()

    async def hash(self, password: str) -> str:
        self.hash_calls.append(password)
        return await self._real.hash(password)

    async def verify(self, password: str, hashed_password: str) -> bool:
        self.verify_calls.append(password)
        return await self._real.verify(password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        return self._real.needs_rehash(hashed_password)

    async def rehash_if_needed(
        self,
        password: str,
        hashed_password: str | None,
    ) -> str | None:
        return await self._real.rehash_if_needed(password, hashed_password)


def _token_manager() -> JWTTokenManager:
    return JWTTokenManager(
        current_key_id="test",
        keys={"test": SecretStr("test_secret_key_12345678901234567890123456789123")},
        access_expiration_hours=1,
        refresh_expiration_days=30,
    )


def _service(
    store: InMemoryUserStore,
    hasher: PasswordHasherProtocol,
) -> AuthenticationService:
    return AuthenticationService(
        password_policy=MagicMock(),
        user_store=store,
        token_manager=_token_manager(),
        password_hasher=hasher,
    )


@pytest.mark.asyncio
async def test_authenticate_user_uses_injected_hasher() -> None:
    store = InMemoryUserStore()
    spy = _SpyHasher()
    service = _service(store, spy)

    result = await service.register_user(
        RegisterRequest(
            name="testuser",
            email="spy@example.com",
            password="Password123!",
            confirm_password="Password123!",
        ),
    )
    assert result.is_ok()
    assert spy.hash_calls == ["Password123!"]

    login = await service.authenticate_user("spy@example.com", "Password123!")
    assert login.is_ok()
    assert spy.verify_calls == ["Password123!"]
    assert isinstance(service._password_hasher, _SpyHasher)


@pytest.mark.asyncio
async def test_composed_hasher_defaults_new_hashes_to_argon2id() -> None:
    composed = ComposedPasswordHasher(
        primary=Argon2idPasswordHasher(kdf=Argon2idKeyDerivation()),
        legacy=PasswordHasher(),
    )
    hashed = await composed.hash("correcthorse")
    assert hashed.startswith("$argon2id$")

    # A stored bcrypt hash still verifies through the legacy shim.
    legacy_hash = await PasswordHasher().hash("correcthorse")
    assert legacy_hash.startswith("$2b$")
    assert await composed.verify("correcthorse", legacy_hash)
    assert not await composed.verify("wrong-password", legacy_hash)

    # Legacy bcrypt hashes are flagged for upgrade (algorithm differs).
    assert composed.needs_rehash(legacy_hash) is True
    upgraded = await composed.rehash_if_needed("correcthorse", legacy_hash)
    assert upgraded is not None
    assert upgraded.startswith("$argon2id$")

    # Argon2id hashes at current parameters are not flagged.
    assert composed.needs_rehash(hashed) is False


@pytest.mark.asyncio
async def test_change_user_password_uses_injected_hasher() -> None:
    store = InMemoryUserStore()
    spy = _SpyHasher()
    service = _service(store, spy)
    service.password_policy.prevent_reuse = False

    result = await service.register_user(
        RegisterRequest(
            name="changepass",
            email="change@example.com",
            password="Password123!",
            confirm_password="Password123!",
        ),
    )
    assert result.is_ok()
    user = result.unwrap()

    changed = await service.change_user_password(
        user.user_id,
        "Password123!",
        "Different123!",
    )
    assert changed.is_ok(), changed.unwrap_err() if changed.is_err() else None
    assert spy.hash_calls == ["Password123!", "Different123!"]
    assert "Password123!" in spy.verify_calls

    old_login = await service.authenticate_user("change@example.com", "Password123!")
    assert old_login.is_err()
    new_login = await service.authenticate_user("change@example.com", "Different123!")
    assert new_login.is_ok()

    creds = await store.get_credentials(user.user_id)
    assert creds is not None
    assert len(creds.previous_hashes) == 1
    assert await spy.verify("Password123!", creds.previous_hashes[0])
