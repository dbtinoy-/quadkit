"""Tests for auth exceptions."""

import pytest

from quadkit.auth.exceptions import (
    AccountLockedError,
    AuthError,
    AuthenticationError,
    AuthorizationError,
    BlacklistedTokenError,
    EmailExistsError,
    InvalidCredentialsError,
    InvalidScopeError,
    InvalidTokenError,
    OAuth2Error,
    PasswordPolicyError,
    TokenError,
    TokenExpiredError,
    UserNotFoundError,
    UsernameExistsError,
)


class TestAuthError:
    """Tests for AuthError."""

    def test_auth_error(self) -> None:
        """Should instantiate."""
        error = AuthError("Auth error")
        assert "Auth error" in str(error)


class TestAuthenticationError:
    """Tests for AuthenticationError."""

    def test_authentication_error(self) -> None:
        """Should instantiate."""
        error = AuthenticationError("Authentication failed")
        assert "Authentication failed" in str(error)


class TestAuthorizationError:
    """Tests for AuthorizationError."""

    def test_authorization_error(self) -> None:
        """Should instantiate."""
        error = AuthorizationError("Not authorized")
        assert "Not authorized" in str(error)


class TestInvalidCredentialsError:
    """Tests for InvalidCredentialsError."""

    def test_invalid_credentials_error(self) -> None:
        """Should instantiate with default message."""
        error = InvalidCredentialsError()
        assert "Invalid credentials" in str(error)

    def test_invalid_credentials_custom_message(self) -> None:
        """Should support custom message."""
        error = InvalidCredentialsError("Wrong password")
        assert "Wrong password" in str(error)


class TestAccountLockedError:
    """Tests for AccountLockedError."""

    def test_account_locked_error(self) -> None:
        """Should instantiate with email."""
        error = AccountLockedError("user@example.com")
        assert "user@example.com" in str(error)
        assert "Account locked" in str(error)

    def test_account_locked_no_email(self) -> None:
        """Should work without email."""
        error = AccountLockedError()
        assert "Account locked" in str(error)


class TestUserNotFoundError:
    """Tests for UserNotFoundError."""

    def test_user_not_found_error(self) -> None:
        """Should instantiate with identifier."""
        error = UserNotFoundError("user123")
        assert "user123" in str(error)
        assert "User not found" in str(error)


class TestTokenError:
    """Tests for TokenError."""

    def test_token_error(self) -> None:
        """Should instantiate."""
        error = TokenError("Token error")
        assert "Token error" in str(error)


class TestInvalidTokenError:
    """Tests for InvalidTokenError."""

    def test_invalid_token_error(self) -> None:
        """Should instantiate."""
        error = InvalidTokenError("Invalid token")
        assert "Invalid token" in str(error)


class TestTokenExpiredError:
    """Tests for TokenExpiredError."""

    def test_token_expired_error(self) -> None:
        """Should instantiate."""
        error = TokenExpiredError("Token expired")
        assert "Token expired" in str(error)


class TestInvalidScopeError:
    """Tests for InvalidScopeError."""

    def test_invalid_scope_error(self) -> None:
        """Should instantiate."""
        error = InvalidScopeError("Invalid scope")
        assert "Invalid scope" in str(error)


class TestBlacklistedTokenError:
    """Tests for BlacklistedTokenError."""

    def test_blacklisted_token_error(self) -> None:
        """Should instantiate."""
        error = BlacklistedTokenError("Token blacklisted")
        assert "Token blacklisted" in str(error)


class TestEmailExistsError:
    """Tests for EmailExistsError."""

    def test_email_exists_error(self) -> None:
        """Should instantiate."""
        error = EmailExistsError("Email exists")
        assert "Email exists" in str(error)


class TestUsernameExistsError:
    """Tests for UsernameExistsError."""

    def test_username_exists_error(self) -> None:
        """Should instantiate."""
        error = UsernameExistsError("Username exists")
        assert "Username exists" in str(error)


class TestPasswordPolicyError:
    """Tests for PasswordPolicyError."""

    def test_password_policy_error(self) -> None:
        """Should instantiate."""
        error = PasswordPolicyError("Password too short")
        assert "Password too short" in str(error)


class TestOAuth2Error:
    """Tests for OAuth2Error."""

    def test_oauth2_error(self) -> None:
        """Should instantiate."""
        error = OAuth2Error("OAuth2 error")
        assert "OAuth2 error" in str(error)
