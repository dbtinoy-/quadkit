"""Token issuance and request authentication share one revocation boundary."""

from __future__ import annotations

import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.config import AuthConfig, JWTConfig
from quadkit.auth.di.bundle_provider import AuthBundleProvider
from quadkit.auth.di.sub_providers.token_provider import TokenProvider
from quadkit.auth.models.user import User
from quadkit.contracts.auth import AuthProviderProtocol, TokenManagerProtocol
from quadkit.di.container import Container
from quadkit.validation import SecretStr

SECRET = "test-only-key-with-more-than-32-characters"  # noqa: S105


def config(*, algorithm="HS256", audience=None):
    return AuthConfig(
        secret_key=SECRET,
        token=JWTConfig(
            secret_key=SECRET, algorithm=algorithm, required_audience=audience
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("audience", [None, "service-a"])
async def test_bundle_uses_same_manager_for_mint_verify_and_revoke(audience):
    bundle = AuthBundleProvider(config=config(audience=audience))
    # A consumer may request the service before registration; it must be
    # rebound too rather than retaining the old private token manager.
    service = bundle._authn.service
    container = Container()
    await bundle.register(container)
    await bundle.boot(container)
    try:
        token_manager = await container.resolve(TokenManagerProtocol)
        authn = await container.resolve(AuthProviderProtocol)
        assert token_manager is authn.token_manager
        assert service.token_manager is token_manager
        user = User(user_id="u-1", email="user@example.test")
        token = token_manager.create_access_token(user)
        verified = await authn.verify_token(token)
        assert verified.is_ok(), verified.unwrap_err()
        assert verified.unwrap().user_id == user.user_id
        assert (await token_manager.logout(token)).is_ok()
        assert (await authn.verify_token(token)).is_err()

        other = token_manager.create_access_token(user)
        assert (await authn.token_manager.logout(other)).is_ok()
        assert (await token_manager.verify_token(other)).is_err()
    finally:
        await bundle.shutdown()


@pytest.mark.asyncio
async def test_zero_config_bundle_can_verify_and_revoke_its_tokens(monkeypatch):
    monkeypatch.setenv("QK_ENV", "development")
    bundle = AuthBundleProvider()
    container = Container()
    await bundle.register(container)
    await bundle.boot(container)
    try:
        token_manager = await container.resolve(TokenManagerProtocol)
        authn = await container.resolve(AuthProviderProtocol)
        assert authn.token_manager is token_manager
        token = token_manager.create_access_token(User(user_id="u-1"))
        assert (await authn.verify_token(token)).is_ok()
        assert (await token_manager.logout(token)).is_ok()
        assert (await authn.verify_token(token)).is_err()
    finally:
        await bundle.shutdown()


@pytest.mark.asyncio
async def test_explicit_manager_is_preserved_across_bundle_protocols():
    manager = JWTTokenManager(
        current_key_id="custom",
        keys={"custom": SecretStr(SECRET)},
        required_audience="custom-service",
    )
    bundle = AuthBundleProvider(config=config(), token_manager=manager)
    container = Container()
    await bundle.register(container)
    await bundle.boot(container)
    try:
        assert await container.resolve(TokenManagerProtocol) is manager
        assert (await container.resolve(AuthProviderProtocol)).token_manager is manager
        token = manager.create_access_token(User(user_id="u-1"))
        assert (await bundle._authn.verify_token(token)).is_ok()
    finally:
        await bundle.shutdown()


@pytest.mark.asyncio
async def test_token_provider_alone_preserves_required_audience():
    provider = TokenProvider(config=config(audience="service-a"))
    container = Container()
    await provider.register(container)
    manager = await container.resolve(TokenManagerProtocol)
    user = User(user_id="u-1")
    valid = manager.create_access_token(user)
    wrong = manager.create_access_token(user, additional_claims={"aud": "other"})
    assert (await manager.verify_token(valid)).is_ok()
    assert (await manager.verify_token(wrong)).is_err()


@pytest.mark.asyncio
async def test_bundle_rsa_uses_shared_key_and_revocation():
    pytest.importorskip("cryptography")
    bundle = AuthBundleProvider(config=config(algorithm="RS256", audience="service-a"))
    container = Container()
    await bundle.register(container)
    await bundle.boot(container)
    try:
        manager = await container.resolve(TokenManagerProtocol)
        authn = await container.resolve(AuthProviderProtocol)
        assert authn.token_manager is manager
        token = manager.create_access_token(User(user_id="u-1"))
        assert (await authn.verify_token(token)).is_ok()
        assert (await manager.logout(token)).is_ok()
        assert (await authn.verify_token(token)).is_err()
    finally:
        await bundle.shutdown()


@pytest.mark.asyncio
async def test_bundle_refuses_an_inconsistent_prebound_token_manager():
    from quadkit.contracts.exceptions import ConfigurationError

    other = JWTTokenManager(current_key_id="other", keys={"other": SecretStr(SECRET)})
    container = Container()
    container.singleton(TokenManagerProtocol, other)
    bundle = AuthBundleProvider(config=config())
    await bundle.register(container)
    with pytest.raises(ConfigurationError, match="same token manager"):
        await bundle.boot(container)


@pytest.mark.asyncio
async def test_bundle_accepts_a_prebound_matching_explicit_token_manager():
    manager = JWTTokenManager(
        current_key_id="custom", keys={"custom": SecretStr(SECRET)}
    )
    container = Container()
    container.singleton(TokenManagerProtocol, manager)
    bundle = AuthBundleProvider(config=config(), token_manager=manager)
    await bundle.register(container)
    await bundle.boot(container)
    try:
        assert (await container.resolve(AuthProviderProtocol)).token_manager is manager
    finally:
        await bundle.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("algorithm", ["RS256", "PS256"])
async def test_bundle_accepts_configured_rsa_private_key(algorithm):
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    settings = AuthConfig(
        secret_key=pem,
        token=JWTConfig(
            secret_key=pem, algorithm=algorithm, required_audience="service-a"
        ),
    )
    bundle = AuthBundleProvider(config=settings)
    container = Container()
    await bundle.register(container)
    await bundle.boot(container)
    try:
        manager = await container.resolve(TokenManagerProtocol)
        authn = await container.resolve(AuthProviderProtocol)
        token = manager.create_access_token(User(user_id="u-1"))
        assert (await authn.verify_token(token)).is_ok()
        assert (await manager.logout(token)).is_ok()
        assert (await authn.verify_token(token)).is_err()
    finally:
        await bundle.shutdown()


@pytest.mark.asyncio
async def test_custom_manager_without_optional_hook_setters_can_boot():
    actual = JWTTokenManager(
        current_key_id="custom", keys={"custom": SecretStr(SECRET)}
    )

    class CustomManager:
        def create_access_token(self, user):
            return actual.create_access_token(user)

        async def verify_token(self, token):
            return await actual.verify_token(token)

        async def logout(self, token):
            return await actual.logout(token)

    manager = CustomManager()
    bundle = AuthBundleProvider(config=config(), token_manager=manager)
    container = Container()
    await bundle.register(container)
    await bundle.boot(container)
    try:
        assert await container.resolve(TokenManagerProtocol) is manager
        token = manager.create_access_token(User(user_id="u-1"))
        assert (await bundle._authn.verify_token(token)).is_ok()
        assert (await manager.logout(token)).is_ok()
        assert (await bundle._authn.verify_token(token)).is_err()
    finally:
        await bundle.shutdown()
