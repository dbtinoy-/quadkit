"""Tests for Result pattern implementation in auth service.

Verifies that auth operations return Result[T, AuthError] types
instead of bare values or raising exceptions.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.auth.exceptions import (
    AuthError,
    InvalidCredentialsError,
    PasswordPolicyError,
    TokenBlacklistedError,
    TokenExpiredError,
)
from quadkit.result import Result
from quadkit.auth.services import AuthServiceWithResultPattern


class TestAuthServiceResultPattern:
    """Test Result pattern in auth service."""

    @pytest.fixture
    def mock_cache(self) -> MagicMock:
        """Create a mock cache backend."""
        cache = MagicMock()
        return cache

    @pytest.fixture
    def auth_service(self, mock_cache: MagicMock) -> AuthServiceWithResultPattern:
        """Create auth service with mock cache."""
        return AuthServiceWithResultPattern(cache=mock_cache)

    @pytest.mark.asyncio
    async def test_validate_password_returns_ok_for_valid_password(
        self, auth_service: AuthServiceWithResultPattern
    ) -> None:
        """Verify validate_password returns Ok for valid password."""
        result = await auth_service.validate_password(
            "ValidPass123",
            min_length=8,
            require_uppercase=True,
            require_digits=True,
        )

        assert result.is_ok()
        assert result.unwrap() is None

    @pytest.mark.asyncio
    async def test_validate_password_returns_err_for_short_password(
        self, auth_service: AuthServiceWithResultPattern
    ) -> None:
        """Verify validate_password returns Err for short password."""
        result = await auth_service.validate_password(
            "Short1",
            min_length=8,
            require_uppercase=True,
            require_digits=True,
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, PasswordPolicyError)

    @pytest.mark.asyncio
    async def test_validate_password_returns_err_for_missing_uppercase(
        self, auth_service: AuthServiceWithResultPattern
    ) -> None:
        """Verify validate_password returns Err without uppercase."""
        result = await auth_service.validate_password(
            "validpass123",
            min_length=8,
            require_uppercase=True,
            require_digits=True,
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, PasswordPolicyError)
        assert "uppercase" in str(error).lower()

    @pytest.mark.asyncio
    async def test_validate_password_returns_err_for_missing_digits(
        self, auth_service: AuthServiceWithResultPattern
    ) -> None:
        """Verify validate_password returns Err without digits."""
        result = await auth_service.validate_password(
            "ValidPass",
            min_length=8,
            require_uppercase=True,
            require_digits=True,
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, PasswordPolicyError)

    @pytest.mark.asyncio
    async def test_verify_credentials_returns_ok_for_valid_credentials(
        self, auth_service: AuthServiceWithResultPattern
    ) -> None:
        """Verify verify_credentials returns Ok(True) for valid credentials."""
        result = await auth_service.verify_credentials(
            username="testuser",
            password="correct_password",
            stored_hash="correct_password",
        )

        assert result.is_ok()
        assert result.unwrap() is True

    @pytest.mark.asyncio
    async def test_verify_credentials_returns_err_for_invalid_password(
        self, auth_service: AuthServiceWithResultPattern
    ) -> None:
        """Verify verify_credentials returns Err for invalid password."""
        result = await auth_service.verify_credentials(
            username="testuser",
            password="wrong_password",
            stored_hash="correct_password",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidCredentialsError)

    @pytest.mark.asyncio
    async def test_verify_credentials_returns_err_for_empty_username(
        self, auth_service: AuthServiceWithResultPattern
    ) -> None:
        """Verify verify_credentials returns Err for empty username."""
        result = await auth_service.verify_credentials(
            username="",
            password="password",
            stored_hash="hash",
        )

        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, InvalidCredentialsError)

    @pytest.mark.asyncio
    async def test_error_hierarchy_correct(self) -> None:
        """Verify error hierarchy is correct."""
        from quadkit.contracts.exceptions.domain import DomainError

        # All auth errors inherit from DomainError
        assert issubclass(AuthError, DomainError)
        assert issubclass(InvalidCredentialsError, AuthError)
        assert issubclass(PasswordPolicyError, AuthError)

        # Instantiate and verify
        auth_err = AuthError("test")
        assert isinstance(auth_err, DomainError)

        invalid_creds = InvalidCredentialsError("invalid")
        assert isinstance(invalid_creds, AuthError)
        assert isinstance(invalid_creds, DomainError)

    @pytest.mark.asyncio
    async def test_error_codes_set_correctly(self) -> None:
        """Verify auth errors have correct error codes."""
        assert AuthError._code == "QK_ERR_AUTH_004"
        assert InvalidCredentialsError._code == "QK_ERR_AUTH_007"
        assert PasswordPolicyError._code == "QK_ERR_AUTH_024"
        assert TokenExpiredError._code == "QK_ERR_AUTH_012"
        assert TokenBlacklistedError._code == "QK_ERR_AUTH_013"

    @pytest.mark.asyncio
    async def test_result_type_available(self) -> None:
        """Verify Result type is available for import."""
        # Should be able to import Result
        assert Result is not None

        # Verify generic form works
        result_type = Result[str, AuthError]
        assert result_type is not None

    @pytest.mark.asyncio
    async def test_cache_token_with_mock_cache(
        self, auth_service: AuthServiceWithResultPattern, mock_cache: MagicMock
    ) -> None:
        """Verify cache_token returns Ok when cache.set succeeds."""
        from quadkit.result import Ok

        # Mock cache.set to return Ok(None)
        mock_cache.set = AsyncMock(return_value=Ok(None))

        result = await auth_service.cache_token(
            token_id="token_123",
            token={"sub": "user_123", "exp": 1234567890},
            ttl=3600,
        )

        assert result.is_ok()
        mock_cache.set.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalidate_token_with_mock_cache(
        self, auth_service: AuthServiceWithResultPattern, mock_cache: MagicMock
    ) -> None:
        """Verify invalidate_token returns Ok when cache.delete succeeds."""
        from quadkit.result import Ok

        # Mock cache.delete to return Ok(True)
        mock_cache.delete = AsyncMock(return_value=Ok(True))

        result = await auth_service.invalidate_token(token_id="token_123")

        assert result.is_ok()
        mock_cache.delete.assert_awaited_once()


class TestAuthErrorInstantiation:
    """Test auth error instantiation."""

    def test_invalid_credentials_error_with_reason(self) -> None:
        """Verify InvalidCredentialsError includes reason."""
        error = InvalidCredentialsError("Password mismatch")
        assert "Password mismatch" in str(error)

    def test_password_policy_error_with_reason(self) -> None:
        """Verify PasswordPolicyError includes reason."""
        error = PasswordPolicyError("Too short")
        assert "Too short" in str(error)

    def test_token_expired_error(self) -> None:
        """Verify TokenExpiredError works."""
        error = TokenExpiredError()
        assert isinstance(error, AuthError)
        assert "expired" in str(error).lower()

    def test_token_blacklisted_error(self) -> None:
        """Verify TokenBlacklistedError works."""
        error = TokenBlacklistedError()
        assert isinstance(error, AuthError)
        assert "revoked" in str(error).lower()


__all__ = [
    "TestAuthServiceResultPattern",
    "TestAuthErrorInstantiation",
]
