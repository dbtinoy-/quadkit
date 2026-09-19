"""Tests for domain constants."""

import pytest

from quadkit.domain.constants import (
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    __version__,
)


class TestDomainConstants:
    """Tests for domain constants."""

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        assert ENV_PREFIX == "QK_DOMAIN__"
        assert isinstance(ENV_PREFIX, str)
        assert ENV_PREFIX.endswith("__")

    def test_env_nested_delimiter(self) -> None:
        """Test nested delimiter constant."""
        assert ENV_NESTED_DELIMITER == "__"
        assert isinstance(ENV_NESTED_DELIMITER, str)

    def test_version_is_string(self) -> None:
        """Test that version is a valid string."""
        assert isinstance(__version__, str)
        assert __version__

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.domain.constants import __all__ as constants_all

        assert "ENV_PREFIX" in constants_all
        assert "ENV_NESTED_DELIMITER" in constants_all