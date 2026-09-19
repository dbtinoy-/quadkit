"""Tests for concurrency constants."""

import pytest

from quadkit.concurrency.constants import (
    DEFAULT_CHANNEL_CAPACITY,
    DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT,
    DEFAULT_WORKER_THREADS,
    ENV_NESTED_DELIMITER,
    ENV_PREFIX,
    __version__,
)


class TestConcurrencyConstants:
    """Tests for concurrency constants."""

    def test_env_prefix(self) -> None:
        """Test environment variable prefix."""
        assert ENV_PREFIX == "QK_CONCURRENCY__"
        assert isinstance(ENV_PREFIX, str)
        assert ENV_PREFIX.endswith("__")

    def test_env_nested_delimiter(self) -> None:
        """Test nested delimiter constant."""
        assert ENV_NESTED_DELIMITER == "__"
        assert isinstance(ENV_NESTED_DELIMITER, str)

    def test_default_channel_capacity(self) -> None:
        """Test default channel capacity."""
        assert DEFAULT_CHANNEL_CAPACITY == 100
        assert isinstance(DEFAULT_CHANNEL_CAPACITY, int)
        assert DEFAULT_CHANNEL_CAPACITY > 0

    def test_default_worker_threads(self) -> None:
        """Test default worker threads."""
        assert DEFAULT_WORKER_THREADS == 4
        assert isinstance(DEFAULT_WORKER_THREADS, int)
        assert DEFAULT_WORKER_THREADS > 0

    def test_default_dispatcher_shutdown_timeout(self) -> None:
        """Test default dispatcher shutdown timeout."""
        assert DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT == 10.0
        assert isinstance(DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT, float)
        assert DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT > 0

    def test_version_is_string(self) -> None:
        """Test that version is a valid string."""
        assert isinstance(__version__, str)
        assert __version__

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.concurrency.constants import __all__ as constants_all

        assert "ENV_PREFIX" in constants_all
        assert "ENV_NESTED_DELIMITER" in constants_all
        assert "DEFAULT_CHANNEL_CAPACITY" in constants_all
        assert "DEFAULT_WORKER_THREADS" in constants_all
        assert "DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT" in constants_all

    def test_timeout_is_reasonable(self) -> None:
        """Test that the shutdown drain timeout is reasonable."""
        assert DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT >= 1.0