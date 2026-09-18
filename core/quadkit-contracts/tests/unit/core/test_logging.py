"""Tests for core logging module."""

from __future__ import annotations

from quadkit.contracts.core.logging import (
    LoggerFactoryProtocol,
    LoggerProtocol,
    RedactorProtocol,
)


class TestLoggerProtocol:
    """Tests for LoggerProtocol."""

    def test_has_debug_method(self) -> None:
        assert hasattr(LoggerProtocol, "debug")

    def test_has_info_method(self) -> None:
        assert hasattr(LoggerProtocol, "info")

    def test_has_warning_method(self) -> None:
        assert hasattr(LoggerProtocol, "warning")

    def test_has_error_method(self) -> None:
        assert hasattr(LoggerProtocol, "error")

    def test_has_critical_method(self) -> None:
        assert hasattr(LoggerProtocol, "critical")

    def test_has_exception_method(self) -> None:
        assert hasattr(LoggerProtocol, "exception")

    def test_has_bind_method(self) -> None:
        assert hasattr(LoggerProtocol, "bind")

    def test_has_unbind_method(self) -> None:
        assert hasattr(LoggerProtocol, "unbind")


class TestLoggerFactoryProtocol:
    """Tests for LoggerFactoryProtocol."""

    def test_has_get_logger_method(self) -> None:
        assert hasattr(LoggerFactoryProtocol, "get_logger")


class TestRedactorProtocol:
    """Tests for RedactorProtocol."""

    def test_has_redact_dict_method(self) -> None:
        assert hasattr(RedactorProtocol, "redact_dict")

    def test_has_redact_value_method(self) -> None:
        assert hasattr(RedactorProtocol, "redact_value")
