"""PasswordHasher and PasswordPolicy tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from quadkit.auth.models import AuthToken
import quadkit.auth as la
from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.schemas import RegisterRequest
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.di import AuthenticationProvider, AuthorizationProvider
from quadkit.auth.storage.db_stores import (
    MongoDBUserStore,
    RedisUserStore,
    SQLUserStore,
)
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.auth.exceptions import (
    TokenExpiredError,
    InvalidTokenError,
    BlacklistedTokenError,
)
from quadkit.auth.exceptions import (
    TokenAudienceError,
    TokenBlacklistedError,
    TokenExpiredError as TokenExpiredErrorAuth,
    TokenInvalidError,
)
from quadkit.contracts.auth.token import VerifiedToken
from quadkit.result import Err, Ok


class TestPasswordHasher:
    """Test password hashing and verification"""

    @pytest.mark.asyncio
    async def test_hash_password(self):
        """Test password hashing"""
        password = "testpassword123"
        hashed = await PasswordHasher().hash(password)

        assert hashed != password
        assert await PasswordHasher().verify(password, hashed)
        # ✅ Verify it's using bcrypt (starts with $2b$ or $2a$)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    @pytest.mark.asyncio
    async def test_hash_uses_12_rounds(self):
        """Test that password hashing uses at least 12 bcrypt rounds"""
        password = "testpassword123"
        hashed = await PasswordHasher(rounds=12).hash(password)

        # Bcrypt format: $2b$12$... (12 rounds)
        parts = hashed.split("$")
        assert len(parts) >= 4
        rounds = int(parts[2])
        assert rounds >= 12, f"Expected >= 12 rounds, got {rounds}"

    @pytest.mark.asyncio
    async def test_verify_password_wrong(self):
        """Test password verification with wrong password"""
        password = "testpassword123"
        wrong_password = "wrongpassword"
        hashed = await PasswordHasher().hash(password)

        assert not await PasswordHasher().verify(wrong_password, hashed)

    @pytest.mark.asyncio
    async def test_verify_password_fallback(self):
        """Test fallback password verification with unknown hash format"""
        # When the hash format is unknown, verify() returns False
        password = "plaintextpassword"
        # This tests the UnknownHashError handling - returns False for invalid hash formats
        assert not await PasswordHasher().verify(password, password)

    @pytest.mark.asyncio
    async def test_hash_long_password(self):
        """Test password hashing with passwords longer than 72 bytes"""
        # Create a password longer than 72 bytes
        long_password = "a" * 100  # 100 characters, > 72 bytes when encoded
        hashed = await PasswordHasher().hash(long_password)

        assert hashed != long_password
        # Should be able to verify with the truncated password
        assert await PasswordHasher().verify(long_password, hashed)
        # Verify it's using bcrypt
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    @pytest.mark.asyncio
    async def test_verify_long_password(self):
        """Test password verification with long passwords"""
        # Create a password longer than 72 bytes
        long_password = "a" * 100
        hashed = await PasswordHasher().hash(long_password)

        # Verification should work with the same long password
        assert await PasswordHasher().verify(long_password, hashed)

        # Verification should fail with wrong password
        assert not await PasswordHasher().verify("wrong" + long_password, hashed)


class TestPasswordPolicy:
    """Test password policy enforcement"""

    def test_valid_password(self):
        """Test valid password - should not raise"""
        policy = PasswordPolicy()
        # validate() raises ValueError if invalid, returns None if valid
        policy.validate("ValidPass123!")  # Should not raise

    def test_password_too_short(self):
        """Test password too short"""
        policy = PasswordPolicy(min_length=8)
        with pytest.raises(ValueError) as exc_info:
            policy.validate("Short1!")
        assert "at least 8 characters" in str(exc_info.value)

    def test_password_missing_uppercase(self):
        """Test password missing uppercase"""
        policy = PasswordPolicy(require_uppercase=True)
        with pytest.raises(ValueError) as exc_info:
            policy.validate("lowercase123!")
        assert "uppercase letter" in str(exc_info.value)

    def test_password_missing_lowercase(self):
        """Test password missing lowercase"""
        policy = PasswordPolicy(require_lowercase=True)
        with pytest.raises(ValueError) as exc_info:
            policy.validate("UPPERCASE123!")
        assert "lowercase letter" in str(exc_info.value)

    def test_password_missing_digit(self):
        """Test password missing digit"""
        policy = PasswordPolicy(require_digits=True)
        with pytest.raises(ValueError) as exc_info:
            policy.validate("Password!")
        assert "digit" in str(exc_info.value)

    def test_password_common(self):
        """Test common password rejection"""
        policy = PasswordPolicy(prevent_common=True)
        with pytest.raises(ValueError) as exc_info:
            policy.validate("password")
        assert "too common" in str(exc_info.value)


