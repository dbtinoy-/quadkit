from datetime import UTC, datetime, timedelta

import jwt
from pydantic import SecretStr
import pytest

from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager


@pytest.mark.asyncio
async def test_key_cleanup_removes_old_keys():
    # Setup manager with a small rotation interval for testability
    manager = JWTTokenManager(
        current_key_id="k1",
        keys={"k1": SecretStr("s1"), "k2": SecretStr("s2")},
        rotation_interval_days=0,
    )

    # artificially set created_at to far past for k1
    old_time = datetime.now(tz=UTC) - timedelta(days=10)
    manager._key_meta["k1"]["created_at"] = old_time

    # ensure k1 is not current and will be removed
    manager.current_key_id = "k2"

    # run cleanup
    await manager._cleanup_old_keys()

    assert "k1" not in manager.keys
    assert "k1" not in manager._key_meta


@pytest.mark.asyncio
async def test_rotate_key_registers_creation_time():
    manager = JWTTokenManager(
        current_key_id="k1",
        keys={"k1": SecretStr("s1")},
        rotation_interval_days=90,
    )

    await manager.rotate_key("k2", SecretStr("s2"))

    assert "k2" in manager.keys
    assert "k2" in manager._key_meta
    assert manager.current_key_id == "k2"


def test_authprovider_rs256_default_generates_keypair():
    from quadkit.auth.config import AuthConfig, JWTConfig
    from quadkit.auth.di.sub_providers.authentication_provider import (
        AuthenticationProvider,
    )

    config = AuthConfig(
        secret_key="test-only-not-for-production-key-32bytes!",
        token=JWTConfig(
            secret_key="test-only-not-for-production-key-32bytes!",
            algorithm="RS256",
        ),
    )
    provider = AuthenticationProvider(config=config)

    # Token manager should have keys with a 'default' kid (dict with private/public)
    keys = provider.token_manager.keys
    assert "default" in keys
    val = keys["default"]
    assert isinstance(val, dict)
    assert "private" in val
    assert "public" in val

    # Creating a token should work
    class UserStub(User):
        pass

    user = User(
        user_id="u1",
        name="u",
        email="e@x.com",
        roles=["user"],
        permissions=["read"],
    )

    token = provider.token_manager.create_access_token(user)
    header = jwt.get_unverified_header(token)
    assert header.get("kid") == "default"
