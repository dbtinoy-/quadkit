"""Tests for app constants."""

import pytest

from quadkit.app.constants import (
    DEFAULT_APP_NAME,
    DEFAULT_HEALTH_CHECK_TIMEOUT,
    DEFAULT_SHUTDOWN_TIMEOUT,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
)


class TestAppConstants:
    """Tests for app constants."""

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        assert ENV_PREFIX == "QK_APP__"
        assert isinstance(ENV_PREFIX, str)
        assert ENV_PREFIX.endswith("__")

    def test_default_app_name(self) -> None:
        """Test default application name."""
        assert DEFAULT_APP_NAME == "quadkit-app"
        assert isinstance(DEFAULT_APP_NAME, str)

    def test_default_shutdown_timeout(self) -> None:
        """Test default shutdown timeout."""
        assert DEFAULT_SHUTDOWN_TIMEOUT == 30.0
        assert isinstance(DEFAULT_SHUTDOWN_TIMEOUT, float)
        assert DEFAULT_SHUTDOWN_TIMEOUT > 0

    def test_default_health_check_timeout(self) -> None:
        """Test default health check timeout."""
        assert DEFAULT_HEALTH_CHECK_TIMEOUT == 5.0
        assert isinstance(DEFAULT_HEALTH_CHECK_TIMEOUT, float)
        assert DEFAULT_HEALTH_CHECK_TIMEOUT > 0

    def test_timeout_order(self) -> None:
        """Test timeout values are in expected order."""
        assert DEFAULT_HEALTH_CHECK_TIMEOUT < DEFAULT_SHUTDOWN_TIMEOUT

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.app.constants import __all__

        assert "ENV_PREFIX" in __all__
        assert "ENV_NESTED_DELIMITER" in __all__
        assert "DEFAULT_APP_NAME" in __all__
        assert "DEFAULT_SHUTDOWN_TIMEOUT" in __all__
        assert "DEFAULT_HEALTH_CHECK_TIMEOUT" in __all__

    def test_env_nested_delimiter(self) -> None:
        """Test nested delimiter constant."""
        assert ENV_NESTED_DELIMITER == "__"
        assert isinstance(ENV_NESTED_DELIMITER, str)
