"""Round 30 hardening pins — driver errors must degrade per the auth contract.

Each test proves that a failure which is NOT one of the builtin
IO/runtime/lookup types (i.e. a real driver/SDK error) is handled by the
documented degradation path instead of escaping as a raw exception:

1. JWTBlacklist.is_blacklisted — any cache failure fails closed (True).
2. Argon2PasswordHasher.verify — malformed input is a mismatch (False).
3. JwtAuthenticator — any verification error rejects the request (None).

Run with: pytest tests/unit/test_round30_hardening.py -v
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.authn.blacklist import JWTBlacklist
from quadkit.auth.authn.password_hasher import Argon2idKeyDerivation, Argon2idPasswordHasher
from quadkit.auth.web.middleware.jwt_authenticator import JwtAuthenticator

pytestmark = pytest.mark.unit


class _DriverError(Exception):
    """Stand-in for a driver/SDK error type (not OSError/ConnectionError)."""


class TestBlacklistFailsClosed:
    async def test_blacklist_check_driver_error_fails_closed(self) -> None:
        import jwt as pyjwt

        cache = MagicMock()
        cache.exists = AsyncMock(side_effect=_DriverError("cache backend down"))

        blacklist = JWTBlacklist(
            cache=cache,
            algorithm="HS256",
            current_key_id_fn=lambda: "key-1",
            access_expiration_hours=1,
            refresh_expiration_days=7,
        )

        # Decodable (signature unverified) token with a subject claim.
        token = pyjwt.encode({"sub": "user-1", "jti": "tok-1"}, "test-signing-key-0123456789abcdef0123456789abcdef", algorithm="HS256")

        # Must not raise — any blacklist-check failure means "treat as revoked".
        assert await blacklist.is_blacklisted(token) is True


class TestPasswordHasherFailsClosed:
    async def test_verify_malformed_hash_returns_false(self) -> None:
        hasher = Argon2idPasswordHasher(kdf=Argon2idKeyDerivation(config=None))

        # argon2 raises InvalidHashError (a pure Exception subclass, NOT
        # VerifyMismatchError/VerificationError) on malformed input.
        # Contract: any verification failure is a mismatch, never a raise.
        assert await hasher.verify("correct horse", "not-a-valid-argon2-hash") is False


class TestJwtAuthenticatorRejectsOnError:
    async def test_verification_driver_error_rejects_request(self) -> None:
        provider = MagicMock()
        provider.verify_token = AsyncMock(side_effect=_DriverError("verifier down"))

        authenticator = JwtAuthenticator(auth_provider=provider)
        authenticator.token_extractor.extract_token = MagicMock(return_value="some.token.here")

        # Must not raise — a request whose token cannot be verified is rejected.
        assert await authenticator.authenticate(request=None) is None
