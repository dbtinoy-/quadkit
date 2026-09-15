"""Tests for logging constants."""

import pytest
from quadkit.logging.constants import (
    CRITICAL,
    DEBUG,
    ERROR,
    INFO,
    WARNING,
)


class TestLoggingConstants:
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
