"""Unit tests for quadkit-middleware constants."""

from quadkit.middleware.constants import (
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_DELAY,
    ENV_PREFIX,
)


class TestMiddlewareConstants:
    """Tests for middleware constants."""

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        assert ENV_PREFIX == "QK_MIDDLEWARE__"
        assert isinstance(ENV_PREFIX, str)

    def test_default_retry_count(self) -> None:
        """Test default retry count."""
        assert DEFAULT_RETRY_COUNT == 3
        assert isinstance(DEFAULT_RETRY_COUNT, int)
        assert DEFAULT_RETRY_COUNT > 0

    def test_default_retry_delay(self) -> None:
        """Test default retry delay."""
        assert DEFAULT_RETRY_DELAY == 0.1
        assert isinstance(DEFAULT_RETRY_DELAY, float)
        assert DEFAULT_RETRY_DELAY >= 0

    def test_all_exports(self) -> None:
        """Test that all constants are properly exported."""
        from quadkit.middleware import constants

        expected = [
            "DEFAULT_RETRY_COUNT",
            "DEFAULT_RETRY_DELAY",
            "ENV_PREFIX",
        ]
        for name in expected:
            assert hasattr(constants, name)
