"""Tests for auth constants."""

import pytest
from quadkit.auth.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
    DEFAULT_TOKEN_ALGORITHM,
    DEFAULT_TOKEN_TYPE,
    DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS,
    DEFAULT_MIN_PASSWORD_LENGTH,
    DEFAULT_MAX_PASSWORD_LENGTH,
    DEFAULT_PASSWORD_HASH_ROUNDS,
    DEFAULT_SESSION_TIMEOUT_MINUTES,
    DEFAULT_SESSION_COOKIE_NAME,
    DEFAULT_SESSION_COOKIE_SECURE,
    DEFAULT_SESSION_COOKIE_HTTPONLY,
    DEFAULT_TOTP_DIGITS,
    DEFAULT_TOTP_INTERVAL,
    DEFAULT_TOTP_VALID_WINDOW,
)


class TestAuthEnvConstants:
    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_AUTH__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"


class TestTokenDefaults:
    def test_access_token_expire_minutes(self) -> None:
        assert DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES == 30

    def test_refresh_token_expire_days(self) -> None:
        assert DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_token_algorithm(self) -> None:
        assert DEFAULT_TOKEN_ALGORITHM == "HS256"

    def test_token_type(self) -> None:
        assert DEFAULT_TOKEN_TYPE == "Bearer"

    def test_jwt_key_rotation_grace_period(self) -> None:
        assert DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS == 3600


class TestPasswordPolicyDefaults:
    def test_min_password_length(self) -> None:
        assert DEFAULT_MIN_PASSWORD_LENGTH == 8

    def test_max_password_length(self) -> None:
        assert DEFAULT_MAX_PASSWORD_LENGTH == 128

    def test_password_hash_rounds(self) -> None:
        assert DEFAULT_PASSWORD_HASH_ROUNDS == 12


class TestSessionDefaults:
    def test_session_timeout_minutes(self) -> None:
        assert DEFAULT_SESSION_TIMEOUT_MINUTES == 60

    def test_session_cookie_name(self) -> None:
        assert DEFAULT_SESSION_COOKIE_NAME == "session"

    def test_session_cookie_secure(self) -> None:
        assert DEFAULT_SESSION_COOKIE_SECURE is True

    def test_session_cookie_httponly(self) -> None:
        assert DEFAULT_SESSION_COOKIE_HTTPONLY is True


class TestMFADefaults:
    def test_totp_digits(self) -> None:
        assert DEFAULT_TOTP_DIGITS == 6

    def test_totp_interval(self) -> None:
        assert DEFAULT_TOTP_INTERVAL == 30

    def test_totp_valid_window(self) -> None:
        assert DEFAULT_TOTP_VALID_WINDOW == 1
