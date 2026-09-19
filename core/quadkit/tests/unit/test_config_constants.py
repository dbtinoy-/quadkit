"""Tests for config constants."""

import pytest

from quadkit.config.constants import (
    DEFAULT_CONFIG_FILENAMES,
    DEFAULT_ENV_VAR_PREFIX,
    DEFAULT_RELOAD_INTERVAL,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    INSECURE_SECRET_VALUES,
    SECRET_FIELD_PATTERNS,
    SUPPORTED_FORMATS,
    __version__,
)


class TestConfigConstants:
    """Tests for config constants."""

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        assert ENV_PREFIX == "QK_CONFIG__"
        assert isinstance(ENV_PREFIX, str)
        assert ENV_PREFIX.endswith("__")

    def test_env_nested_delimiter(self) -> None:
        """Test nested delimiter constant."""
        assert ENV_NESTED_DELIMITER == "__"
        assert isinstance(ENV_NESTED_DELIMITER, str)

    def test_default_config_filenames(self) -> None:
        """Test default config filenames."""
        assert isinstance(DEFAULT_CONFIG_FILENAMES, list)
        assert "application.yml" in DEFAULT_CONFIG_FILENAMES
        assert "application.yaml" in DEFAULT_CONFIG_FILENAMES
        assert len(DEFAULT_CONFIG_FILENAMES) == 2

    def test_default_env_var_prefix(self) -> None:
        """Test default env var prefix."""
        assert DEFAULT_ENV_VAR_PREFIX == "QK_"
        assert isinstance(DEFAULT_ENV_VAR_PREFIX, str)
        assert not DEFAULT_ENV_VAR_PREFIX.endswith("__")

    def test_supported_formats(self) -> None:
        """Test supported formats."""
        assert isinstance(SUPPORTED_FORMATS, frozenset)
        assert "yaml" in SUPPORTED_FORMATS
        assert "yml" in SUPPORTED_FORMATS
        assert "json" in SUPPORTED_FORMATS

    def test_default_reload_interval(self) -> None:
        """Test default reload interval."""
        assert DEFAULT_RELOAD_INTERVAL == 30.0
        assert isinstance(DEFAULT_RELOAD_INTERVAL, float)
        assert DEFAULT_RELOAD_INTERVAL > 0

    def test_version_is_string(self) -> None:
        """Test that version is a valid string."""
        assert isinstance(__version__, str)
        assert __version__

    def test_insecure_secret_values(self) -> None:
        """Test insecure secret values."""
        assert isinstance(INSECURE_SECRET_VALUES, frozenset)
        assert "password" in INSECURE_SECRET_VALUES
        assert "secret" in INSECURE_SECRET_VALUES
        assert "example" in INSECURE_SECRET_VALUES
        assert len(INSECURE_SECRET_VALUES) > 10

    def test_secret_field_patterns(self) -> None:
        """Test secret field patterns."""
        assert isinstance(SECRET_FIELD_PATTERNS, frozenset)
        assert "password" in SECRET_FIELD_PATTERNS
        assert "secret" in SECRET_FIELD_PATTERNS
        assert "token" in SECRET_FIELD_PATTERNS
        assert "api_key" in SECRET_FIELD_PATTERNS

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.config.constants import __all__ as constants_all

        assert "ENV_PREFIX" in constants_all
        assert "ENV_NESTED_DELIMITER" in constants_all
        assert "DEFAULT_CONFIG_FILENAMES" in constants_all
        assert "DEFAULT_ENV_VAR_PREFIX" in constants_all
        assert "SUPPORTED_FORMATS" in constants_all
        assert "DEFAULT_RELOAD_INTERVAL" in constants_all
        assert "INSECURE_SECRET_VALUES" in constants_all
        assert "SECRET_FIELD_PATTERNS" in constants_all

    def test_secret_field_patterns_are_lowercase(self) -> None:
        """Test that secret field patterns are lowercase."""
        for pattern in SECRET_FIELD_PATTERNS:
            assert pattern.islower(), f"Pattern {pattern!r} is not lowercase"

    def test_insecure_secret_values_are_lowercase(self) -> None:
        """Test that insecure secret values are lowercase."""
        for value in INSECURE_SECRET_VALUES:
            assert value.islower(), f"Value {value!r} is not lowercase"