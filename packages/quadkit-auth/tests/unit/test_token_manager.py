from unittest.mock import AsyncMock

import jwt
import pytest

import quadkit.auth as la
from quadkit.auth.config import AuthConfig, JWTConfig


@pytest.fixture
def mock_cache():
    return AsyncMock()


@pytest.mark.asyncio
async def test_verify_token_rejects_invalid_alg(mock_cache):
    _key = "secret" * 8
    config = AuthConfig(secret_key=_key, token=JWTConfig(secret_key=_key))
    ap = la.AuthenticationProvider(config=config, cache_service=mock_cache)
    # Craft a token whose header declares RS256 (not accepted by HS256 server)
    header_b64 = "eyJhbGciOiJSUzI1NiIsImtpZCI6ImRlZmF1bHQifQ"
    payload_b64 = "eyJzdWIiOiJ1c2VyLTEyMyJ9"
    fake_token = f"{header_b64}.{payload_b64}.invalidsig"

    result = await ap.verify_token(fake_token)
    assert result.is_err()


@pytest.mark.asyncio
async def test_verify_token_accepts_valid_hs256_token(mock_cache):
    # Use standard secret for testing
    secret = "test_secret_key_at_least_32_chars_long"
    mock_cache.exists.return_value = False
    config = AuthConfig(secret_key=secret, token=JWTConfig(secret_key=secret))
    ap = la.AuthenticationProvider(config=config, cache_service=mock_cache)
    payload = {"sub": "user-xyz", "type": "access", "aud": None}
    key = secret

    # Generate token using pyjwt for external verification
    token = jwt.encode(
        payload,
        key,
        algorithm="HS256",
    )

    result = await ap.verify_token(token)
    assert result.is_ok()
    verified = result.unwrap()
    assert verified.user_id == "user-xyz"
