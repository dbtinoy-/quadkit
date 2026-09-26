import pytest

from quadkit.auth.authn.security import PasswordHasher
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.mfa.manager import MFAManager
from quadkit.auth.storage.token_store import InMemoryUserStore


async def _make_user(
    user_store: InMemoryUserStore, name: str, email: str, password: str
):
    """Helper: hash password and create user directly in the store."""
    hashed = await PasswordHasher().hash(password)
    return await user_store.create_user(name=name, email=email, hashed_password=hashed)


@pytest.mark.asyncio
async def test_enable_and_verify_totp():
    user_store = InMemoryUserStore()
    mfa_service = MFAManager(user_store)
    provider = AuthenticationProvider(
        user_store=user_store,
        mfa_service=mfa_service,
    )

    user = await _make_user(user_store, "mfauser", "mfa@example.com", "Password1A")

    secret, uri, backup_codes = await provider.mfa_service.enable_totp(
        user.user_id,
        issuer="TestCo",
    )

    assert secret is not None
    assert len(secret) > 0
    assert uri.startswith("otpauth://totp/")
    assert len(backup_codes) >= 8

    # Use generated secret to compute current code and verify
    from quadkit.auth.authn.mfa import generate_totp_code

    code = generate_totp_code(secret)
    ok = await provider.mfa_service.verify_totp(user.user_id, code)
    assert ok


@pytest.mark.asyncio
async def test_backup_code_consumption():
    user_store = InMemoryUserStore()
    mfa_service = MFAManager(user_store)
    provider = AuthenticationProvider(
        user_store=user_store,
        mfa_service=mfa_service,
    )
    user = await _make_user(user_store, "mfbuser", "mfb@example.com", "Password1A")

    _secret, _uri, backup_codes = await provider.mfa_service.enable_totp(
        user.user_id,
        issuer="TestCo",
    )
    # Use a backup code
    code = backup_codes[0]

    ok = await provider.mfa_service.verify_totp(user.user_id, code)
    assert ok

    # Second use should fail
    ok2 = await provider.mfa_service.verify_totp(user.user_id, code)
    assert not ok2


@pytest.mark.asyncio
async def test_disable_totp():
    user_store = InMemoryUserStore()
    mfa_service = MFAManager(user_store)
    provider = AuthenticationProvider(
        user_store=user_store,
        mfa_service=mfa_service,
    )
    user = await _make_user(user_store, "mfad", "mfad@example.com", "Password1A")

    secret, _uri, _backup_codes = await provider.mfa_service.enable_totp(
        user.user_id,
        issuer="TestCo",
    )
    ok = await provider.mfa_service.disable_totp(user.user_id)
    assert ok

    # Now verification should fail
    from quadkit.auth.authn.mfa import generate_totp_code

    code = generate_totp_code(secret)
    ok2 = await provider.mfa_service.verify_totp(user.user_id, code)
    assert not ok2
