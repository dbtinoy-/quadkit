"""Tests for auth types enums."""

import pytest
from quadkit.auth.types import AuthStatus, TokenType, UserStatus


class TestAuthStatus:
    def test_authenticated(self) -> None:
        assert AuthStatus.AUTHENTICATED == "authenticated"

    def test_unauthenticated(self) -> None:
        assert AuthStatus.UNAUTHENTICATED == "unauthenticated"

    def test_token_expired(self) -> None:
        assert AuthStatus.TOKEN_EXPIRED == "token_expired"

    def test_token_invalid(self) -> None:
        assert AuthStatus.TOKEN_INVALID == "token_invalid"

    def test_user_inactive(self) -> None:
        assert AuthStatus.USER_INACTIVE == "user_inactive"

    def test_user_not_verified(self) -> None:
        assert AuthStatus.USER_NOT_VERIFIED == "user_not_verified"


class TestTokenType:
    def test_bearer(self) -> None:
        assert TokenType.BEARER == "Bearer"

    def test_basic(self) -> None:
        assert TokenType.BASIC == "Basic"

    def test_api_key(self) -> None:
        assert TokenType.API_KEY == "ApiKey"


class TestUserStatus:
    def test_active(self) -> None:
        assert UserStatus.ACTIVE == "active"

    def test_inactive(self) -> None:
        assert UserStatus.INACTIVE == "inactive"

    def test_suspended(self) -> None:
        assert UserStatus.SUSPENDED == "suspended"

    def test_pending_verification(self) -> None:
        assert UserStatus.PENDING_VERIFICATION == "pending_verification"

    def test_deleted(self) -> None:
        assert UserStatus.DELETED == "deleted"
