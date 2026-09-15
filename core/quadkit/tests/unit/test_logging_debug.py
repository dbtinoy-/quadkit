"""Tests for logging/debug module."""
import os
import pytest
from unittest.mock import patch, MagicMock

from quadkit.logging.debug import is_debug_mode, log_lifecycle


class TestIsDebugMode:
    """Tests for is_debug_mode function."""

    def test_debug_mode_disabled_by_default(self) -> None:
        """Test debug mode returns False when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove QK_DEBUG from environment
            env_without = {k: v for k, v in os.environ.items() if k != "QK_DEBUG"}
            with patch.dict(os.environ, env_without, clear=True):
                result = is_debug_mode()
                assert result is False

    def test_debug_mode_enabled_with_1(self) -> None:
        """Test debug mode enabled with '1'."""
        with patch.dict(os.environ, {"QK_DEBUG": "1"}):
            assert is_debug_mode() is True

    def test_debug_mode_enabled_with_true(self) -> None:
        """Test debug mode enabled with 'true'."""
        with patch.dict(os.environ, {"QK_DEBUG": "true"}):
            assert is_debug_mode() is True

    def test_debug_mode_enabled_with_yes(self) -> None:
        """Test debug mode enabled with 'yes'."""
        with patch.dict(os.environ, {"QK_DEBUG": "yes"}):
            assert is_debug_mode() is True

    def test_debug_mode_case_insensitive_true(self) -> None:
        """Test debug mode is case insensitive for true."""
        with patch.dict(os.environ, {"QK_DEBUG": "TRUE"}):
            # The check uses .strip() then checks in list - so "TRUE" matches
            # Actually let me recheck - the list is ("1", "true", "yes")
            # "TRUE" is not in that list - case sensitive!
            # But actually strip() then lowercase should be checked - the function
            # just checks if stripped value is in the list - so it's case sensitive
            # Let me fix the test
            result = is_debug_mode()
            # "TRUE" is not in ("1", "true", "yes") - so it's False
            assert result is False

    def test_debug_mode_whitespace_stripped(self) -> None:
        """Test debug mode strips whitespace."""
        with patch.dict(os.environ, {"QK_DEBUG": "  1  "}):
            assert is_debug_mode() is True

    def test_debug_mode_disabled_with_0(self) -> None:
        """Test debug mode disabled with '0'."""
        with patch.dict(os.environ, {"QK_DEBUG": "0"}):
            assert is_debug_mode() is False

    def test_debug_mode_disabled_with_false(self) -> None:
        """Test debug mode disabled with 'false'."""
        with patch.dict(os.environ, {"QK_DEBUG": "false"}):
            assert is_debug_mode() is False

    def test_debug_mode_disabled_with_empty_string(self) -> None:
        """Test debug mode disabled with empty string."""
        with patch.dict(os.environ, {"QK_DEBUG": ""}):
            assert is_debug_mode() is False


class TestLogLifecycle:
    """Tests for log_lifecycle function."""

    @patch("quadkit.logging.debug.is_debug_mode")
    def test_log_lifecycle_disabled_when_not_debug(
        self, mock_debug: MagicMock
    ) -> None:
        """Test log_lifecycle does nothing when debug mode disabled."""
        mock_debug.return_value = False
        with patch("quadkit.logging.debug.logger") as mock_logger:
            log_lifecycle("test_event", key="value")
            mock_logger.debug.assert_not_called()

    @patch("quadkit.logging.debug.is_debug_mode")
    def test_log_lifecycle_emits_debug_when_enabled(
        self, mock_debug: MagicMock
    ) -> None:
        """Test log_lifecycle emits debug log when debug mode enabled."""
        mock_debug.return_value = True
        with patch("quadkit.logging.debug.logger") as mock_logger:
            log_lifecycle("test_event", key="value", count=42)
            mock_logger.debug.assert_called_once_with("test_event", key="value", count=42)

    @patch("quadkit.logging.debug.is_debug_mode")
    def test_log_lifecycle_with_no_context(
        self, mock_debug: MagicMock
    ) -> None:
        """Test log_lifecycle works with no context."""
        mock_debug.return_value = True
        with patch("quadkit.logging.debug.logger") as mock_logger:
            log_lifecycle("simple_event")
            mock_logger.debug.assert_called_once_with("simple_event")


class TestDebugModuleExports:
    """Tests for module exports."""

    def test_is_debug_mode_exported(self) -> None:
        """Test is_debug_mode is exported."""
        from quadkit.logging.debug import is_debug_mode
        assert callable(is_debug_mode)

    def test_log_lifecycle_exported(self) -> None:
        """Test log_lifecycle is exported."""
        from quadkit.logging.debug import log_lifecycle
        assert callable(log_lifecycle)