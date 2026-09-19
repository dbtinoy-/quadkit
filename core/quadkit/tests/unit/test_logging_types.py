"""Tests for logging types."""

import pytest

from quadkit.logging.types import LogLevel


class TestLogLevel:
    """Tests for LogLevel enum."""

    def test_log_level_values(self) -> None:
        """Test LogLevel enum values."""
        assert LogLevel.DEBUG.value == "debug"
        assert LogLevel.INFO.value == "info"
        assert LogLevel.WARNING.value == "warning"
        assert LogLevel.ERROR.value == "error"
        assert LogLevel.CRITICAL.value == "critical"

    def test_log_level_members(self) -> None:
        """Test LogLevel has expected members."""
        members = list(LogLevel)
        assert len(members) == 5

    def test_log_level_from_string(self) -> None:
        """Test creating LogLevel from string."""
        assert LogLevel("debug") == LogLevel.DEBUG
        assert LogLevel("error") == LogLevel.ERROR

    def test_log_level_order(self) -> None:
        """Test LogLevel ordering."""
        assert LogLevel.DEBUG.as_int < LogLevel.INFO.as_int
        assert LogLevel.INFO.as_int < LogLevel.WARNING.as_int
        assert LogLevel.WARNING.as_int < LogLevel.ERROR.as_int
        assert LogLevel.ERROR.as_int < LogLevel.CRITICAL.as_int
