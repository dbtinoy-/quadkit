"""Tests for config constants."""

from __future__ import annotations

from quadkit.config.constants import (
    DEFAULT_CONFIG_FILENAMES,
    DEFAULT_ENV_VAR_PREFIX,
    DEFAULT_RELOAD_INTERVAL,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    INSECURE_SECRET_VALUES,
    SECRET_FIELD_PATTERNS,
    SUPPORTED_FORMATS,
)


class TestConfigConstants:
    """Tests for config constants."""

    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_CONFIG__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"

    def test_default_config_filenames(self) -> None:
        assert DEFAULT_CONFIG_FILENAMES == ["application.yml", "application.yaml"]

    def test_default_env_var_prefix(self) -> None:
        assert DEFAULT_ENV_VAR_PREFIX == "QK_"

    def test_supported_formats(self) -> None:
        assert frozenset({"yaml", "yml", "json"}) == SUPPORTED_FORMATS

    def test_default_reload_interval(self) -> None:
        assert DEFAULT_RELOAD_INTERVAL == 30.0


class TestSecretDetection:
    """Tests for secret detection constants."""

    def test_insecure_secret_values_is_frozenset(self) -> None:
        assert isinstance(INSECURE_SECRET_VALUES, frozenset)

    def test_insecure_secret_values_contains_placeholder(self) -> None:
        assert "placeholder" in INSECURE_SECRET_VALUES

    def test_insecure_secret_values_contains_password(self) -> None:
        assert "password" in INSECURE_SECRET_VALUES

    def test_secret_field_patterns_is_frozenset(self) -> None:
        assert isinstance(SECRET_FIELD_PATTERNS, frozenset)

    def test_secret_field_patterns_contains_password(self) -> None:
        assert "password" in SECRET_FIELD_PATTERNS

    def test_secret_field_patterns_contains_token(self) -> None:
        assert "token" in SECRET_FIELD_PATTERNS

    def test_secret_field_patterns_contains_api_key(self) -> None:
        assert "api_key" in SECRET_FIELD_PATTERNS
