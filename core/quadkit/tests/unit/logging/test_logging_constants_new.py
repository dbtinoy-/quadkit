"""Tests for logging constants."""

from __future__ import annotations

from quadkit.logging.constants import CRITICAL, DEBUG, ERROR, INFO, WARNING


class TestLogLevels:
    """Tests for log level constants."""

    def test_critical(self) -> None:
        assert CRITICAL == "critical"

    def test_debug(self) -> None:
        assert DEBUG == "debug"

    def test_error(self) -> None:
        assert ERROR == "error"

    def test_info(self) -> None:
        assert INFO == "info"

    def test_warning(self) -> None:
        assert WARNING == "warning"

    def test_all_levels_are_strings(self) -> None:
        levels = [CRITICAL, DEBUG, ERROR, INFO, WARNING]
        for level in levels:
            assert isinstance(level, str)