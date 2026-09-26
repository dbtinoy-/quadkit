"""Tests for PasswordConfig in AuthConfig."""

from __future__ import annotations

import pytest

from quadkit.auth.config import AuthConfig, PasswordConfig


class TestPasswordConfigDefaults:
    def test_default_min_length(self) -> None:
        config = PasswordConfig()
        assert config.min_length == 12

    def test_default_max_length(self) -> None:
        config = PasswordConfig()
        assert config.max_length == 128

    def test_complexity_flags_defaults(self) -> None:
        config = PasswordConfig()
        assert config.require_uppercase  # True by default
        assert not config.require_lowercase  # False by default
        assert config.require_digits  # True by default
        assert not config.require_special  # False by default

    def test_banned_patterns_empty_by_default(self) -> None:
        config = PasswordConfig()
        assert config.banned_patterns == []

    def test_default_bcrypt_rounds(self) -> None:
        config = PasswordConfig()
        assert config.bcrypt_rounds == 12

    def test_default_argon2_cost_factors(self) -> None:
        config = PasswordConfig()
        assert config.argon2_memory_cost == 65536
        assert config.argon2_time_cost == 3
        assert config.argon2_parallelism == 4

    def test_rejects_weak_rounds_in_production(self, monkeypatch) -> None:
        monkeypatch.setenv("QK_ENV", "production")
        with pytest.raises(ValueError):
            PasswordConfig(bcrypt_rounds=4)

    def test_rejects_low_argon2_memory_in_production(self, monkeypatch) -> None:
        monkeypatch.setenv("QK_ENV", "staging")
        with pytest.raises(ValueError):
            PasswordConfig(argon2_memory_cost=8192)

    def test_allows_weak_rounds_in_dev(self, monkeypatch) -> None:
        monkeypatch.setenv("QK_ENV", "development")
        config = PasswordConfig(bcrypt_rounds=4, argon2_memory_cost=8192)
        assert config.bcrypt_rounds == 4
        assert config.argon2_memory_cost == 8192

    def test_custom_values(self) -> None:
        config = PasswordConfig(
            min_length=12,
            max_length=64,
            require_uppercase=True,
            require_digits=True,
            banned_patterns=["password", "letmein"],
        )
        assert config.min_length == 12
        assert config.max_length == 64
        assert config.require_uppercase
        assert config.require_digits
        assert "password" in config.banned_patterns


class TestAuthConfigPassword:
    def test_password_field_has_default(self) -> None:
        """AuthConfig must expose a `password` field with a PasswordConfig default."""
        config = AuthConfig(secret_key="test-key", token={"secret_key": "test-key"})
        assert isinstance(config.password, PasswordConfig)

    def test_password_field_is_configurable(self) -> None:
        config = AuthConfig(
            secret_key="test-key",
            token={"secret_key": "test-key"},
            password={"min_length": 16, "require_digits": True},
        )
        assert config.password.min_length == 16
        assert config.password.require_digits
