from unittest.mock import AsyncMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import SecretStr
import jwt
import pytest

import quadkit.auth as la
from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager


@pytest.fixture
def user() -> User:
    return User(
        user_id="user-123",
        name="testuser",
        email="test@example.com",
        roles=["user"],
        permissions=["read"],
    )


@pytest.fixture
def mock_cache():
    mock = AsyncMock()
    mock.exists.return_value = False
    return mock


def _generate_rsa_keypair():
    # Generate a 2048-bit RSA key for tests
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    return private_pem.decode("utf-8"), public_pem.decode("utf-8")


def test_rs256_sign_and_verify(user, mock_cache):
    private_pem, public_pem = _generate_rsa_keypair()

    # Use SecretStr to avoid deprecation warnings
    keys = {"rsa-1": {
        "private": SecretStr(private_pem),
        "public": SecretStr(public_pem)
    }}

    manager = JWTTokenManager(
        current_key_id="rsa-1",
        keys=keys,
        algorithm="RS256",
        cache_service=mock_cache
    )

    token = manager.create_access_token(user)

    header = jwt.get_unverified_header(token)
    assert header.get("kid") == "rsa-1"

    # Verify with public key directly
    payload = jwt.decode(token, public_pem, algorithms=["RS256"])
    assert payload["sub"] == user.user_id


@pytest.mark.asyncio
async def test_rs256_key_rotation(user, mock_cache):
    priv1, pub1 = _generate_rsa_keypair()
    priv2, pub2 = _generate_rsa_keypair()

    # Use SecretStr to avoid deprecation warnings
    keys = {"k1": {
        "private": SecretStr(priv1),
        "public": SecretStr(pub1)
    }}
    manager = JWTTokenManager(
        current_key_id="k1",
        keys=keys,
        algorithm="RS256",
        cache_service=mock_cache
    )

    token1 = manager.create_access_token(user)

    # Rotate to new key (asymmetric dict accepted)
    await manager.rotate_key("k2", {"private": SecretStr(priv2), "public": SecretStr(pub2)})

    # Old token should still verify
    result1 = await manager.verify_token(token1, "access")
    assert result1.is_ok()

    # New tokens should use new key
    token2 = manager.create_access_token(user)
    header2 = jwt.get_unverified_header(token2)
    assert header2.get("kid") == "k2"

    result2 = await manager.verify_token(token2, "access")
    assert result2.is_ok()

    # Remove old key and ensure old token fails
    del manager.keys["k1"]
    result3 = await manager.verify_token(token1, "access")
    assert result3.is_err()
