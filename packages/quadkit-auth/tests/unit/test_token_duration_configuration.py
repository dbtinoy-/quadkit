"""JWTConfig durations must control issuance, verification and revocation TTLs."""

from __future__ import annotations

from unittest.mock import AsyncMock

import jwt
import pytest

from quadkit.auth.config import AuthConfig, JWTConfig
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.di.sub_providers.authentication_provider import AuthenticationProvider
from quadkit.auth.di.sub_providers.token_provider import TokenProvider
from quadkit.auth.models.user import User
from quadkit.contracts.auth import AuthProviderProtocol, TokenManagerProtocol
from quadkit.contracts.core import Duration
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.di.container import Container

SECRET = "token-test-secret-longer-than-thirty-two-characters"  # noqa: S105


def config(**durations):
    return AuthConfig(
        secret_key=SECRET, token=JWTConfig(secret_key=SECRET, **durations)
    )


def lifetime(token):
    # Inspect only locally generated claims; production verification is signed.
    claims = jwt.decode(token, options={"verify_signature": False})
    return claims["exp"] - claims["iat"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("durations", "access", "refresh", "grace"),
    [
        ({}, 1800, 7 * 86400, 3600),
        (
            {
                "access_token_expire": Duration.seconds(90),
                "refresh_token_expire": Duration.minutes(150),
                "key_rotation_grace_period": Duration.zero(),
            },
            90,
            9000,
            0,
        ),
    ],
)
async def test_bundle_tokens_use_configured_durations(
    durations, access, refresh, grace
):
    bundle = AuthBundleProvider(config=config(**durations))
    container = Container()
    await bundle.register(container)
    await bundle.boot(container)
    try:
        manager = await container.resolve(TokenManagerProtocol)
        authn = await container.resolve(AuthProviderProtocol)
        user = User(user_id="u-1")
        access_token = manager.create_access_token(user)
        refresh_token = manager.create_refresh_token(user)
        assert lifetime(access_token) == access
        assert lifetime(refresh_token) == refresh
        assert manager.grace_period_seconds == grace
        assert authn.token_manager is manager
        assert (await authn.verify_token(access_token)).is_ok()
    finally:
        await bundle.shutdown()


def test_standalone_authentication_provider_also_honors_duration_config():
    authn = AuthenticationProvider(
        config=config(
            access_token_expire=Duration.minutes(2),
            refresh_token_expire=Duration.hours(12),
            key_rotation_grace_period=Duration.minutes(3),
        )
    )
    assert lifetime(authn.token_manager.create_access_token(User(user_id="u-1"))) == 120
    assert (
        lifetime(authn.token_manager.create_refresh_token(User(user_id="u-1"))) == 43200
    )
    assert authn.token_manager.grace_period_seconds == 180


@pytest.mark.asyncio
async def test_explicit_legacy_overrides_take_precedence():
    provider = TokenProvider(
        config=config(
            access_token_expire=Duration.minutes(2),
            refresh_token_expire=Duration.hours(1),
        ),
        jwt_access_expiration_hours=2,
        jwt_refresh_expiration_days=3,
    )
    container = Container()
    await provider.register(container)
    manager = await container.resolve(TokenManagerProtocol)
    user = User(user_id="u-1")
    assert lifetime(manager.create_access_token(user)) == 7200
    assert lifetime(manager.create_refresh_token(user)) == 3 * 86400


@pytest.mark.parametrize(
    ("field", "seconds"),
    [
        ("access_token_expire", 0),
        ("access_token_expire", -1),
        ("refresh_token_expire", 0),
        ("refresh_token_expire", float("inf")),
        ("key_rotation_grace_period", -1),
        ("key_rotation_grace_period", float("nan")),
    ],
)
def test_invalid_durations_fail_closed(field, seconds):
    settings = config(**{field: Duration.seconds(seconds)})
    with pytest.raises(ConfigurationError, match="Invalid"):
        TokenProvider(config=settings)
    with pytest.raises(ConfigurationError, match="Invalid"):
        AuthenticationProvider(config=settings)


@pytest.mark.asyncio
async def test_revocation_ttl_rounds_up_to_cover_fractional_lifetimes():
    cache = AsyncMock()
    cache.set.return_value = True
    provider = TokenProvider(
        config=config(
            access_token_expire=Duration.seconds(1.1),
            refresh_token_expire=Duration.seconds(2.1),
        ),
        cache_service=cache,
    )
    container = Container()
    await provider.register(container)
    manager = await container.resolve(TokenManagerProtocol)
    assert (await manager.logout_all_user_tokens("u-1")).is_ok()
    assert cache.set.await_args.kwargs["ttl"] == 3


@pytest.mark.asyncio
async def test_rotation_grace_starts_when_the_old_key_is_retired():
    from datetime import UTC, datetime, timedelta

    provider = TokenProvider(
        config=config(key_rotation_grace_period=Duration.seconds(90))
    )
    container = Container()
    await provider.register(container)
    manager = await container.resolve(TokenManagerProtocol)
    token = manager.create_access_token(User(user_id="u-1"))
    old_id = manager.current_key_id
    manager._key_meta[old_id]["created_at"] = datetime(2000, 1, 1, tzinfo=UTC)
    await manager.rotate_key("new", "another-test-secret-longer-than-32-characters")
    assert old_id in manager.keys
    assert (await manager.verify_token(token)).is_ok()
    manager._key_meta[old_id]["retired_at"] = datetime.now(UTC) - timedelta(seconds=91)
    await manager._cleanup_old_keys()
    assert old_id not in manager.keys
    assert (await manager.verify_token(token)).is_err()
