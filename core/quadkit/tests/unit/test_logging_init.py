"""Tests for logging/__init__.py lazy imports."""

import pytest


class TestLoggingLazyImports:
    """Test lazy imports from logging module."""

    def test_import_get_logger(self) -> None:
        """Test lazy import of get_logger."""
        from quadkit.logging import get_logger
        assert callable(get_logger)

    def test_import_logger_factory(self) -> None:
        """Test lazy import of LoggerFactoryProtocol."""
        from quadkit.logging import LoggerFactoryProtocol
        assert LoggerFactoryProtocol is not None

    def test_import_logger_factory_impl(self) -> None:
        """Test lazy import of LoggerFactoryImpl."""
        from quadkit.logging import LoggerFactoryImpl
        assert LoggerFactoryImpl is not None

    def test_import_logger_protocol(self) -> None:
        """Test lazy import of LoggerProtocol."""
        from quadkit.logging import LoggerProtocol
        assert LoggerProtocol is not None

    def test_import_logger_alias(self) -> None:
        """Test lazy import of Logger (alias for LoggerProtocol)."""
        from quadkit.logging import Logger
        assert Logger is not None

    def test_import_redactor_protocol(self) -> None:
        """Test lazy import of RedactorProtocol."""
        from quadkit.logging import RedactorProtocol
        assert RedactorProtocol is not None

    def test_import_configure_logging(self) -> None:
        """Test lazy import of configure_logging."""
        from quadkit.logging import configure_logging
        assert callable(configure_logging)

    def test_import_apply_config(self) -> None:
        """Test lazy import of apply_config."""
        from quadkit.logging import apply_config
        assert callable(apply_config)

    def test_import_logging_config(self) -> None:
        """Test lazy import of LoggingConfig."""
        from quadkit.logging import LoggingConfig
        assert LoggingConfig is not None

    def test_import_logging_provider(self) -> None:
        """Test lazy import of LoggingProvider."""
        from quadkit.logging import LoggingProvider
        assert LoggingProvider is not None

    def test_import_log_level(self) -> None:
        """Test lazy import of LogLevel."""
        from quadkit.logging import LogLevel
        assert LogLevel is not None

    def test_import_critical(self) -> None:
        """Test lazy import of CRITICAL."""
        from quadkit.logging import CRITICAL
        assert CRITICAL is not None

    def test_import_debug(self) -> None:
        """Test lazy import of DEBUG."""
        from quadkit.logging import DEBUG
        assert DEBUG is not None

    def test_import_error(self) -> None:
        """Test lazy import of ERROR."""
        from quadkit.logging import ERROR
        assert ERROR is not None

    def test_import_info(self) -> None:
        """Test lazy import of INFO."""
        from quadkit.logging import INFO
        assert INFO is not None

    def test_import_warning(self) -> None:
        """Test lazy import of WARNING."""
        from quadkit.logging import WARNING
        assert WARNING is not None

    def test_import_query_log_entry(self) -> None:
        """Test lazy import of QueryLogEntry."""
        from quadkit.logging import QueryLogEntry
        assert QueryLogEntry is not None

    def test_import_query_logger_protocol(self) -> None:
        """Test lazy import of QueryLoggerProtocol."""
        from quadkit.logging import QueryLoggerProtocol
        assert QueryLoggerProtocol is not None


class TestLoggingDir:
    """Test __dir__ returns expected keys."""

    def test_dir_contains_expected(self) -> None:
        """Test __dir__ contains expected attributes."""
        from quadkit import logging
        attrs = dir(logging)
        assert "get_logger" in attrs
        assert "Logger" in attrs
        assert "LoggerFactoryProtocol" in attrs
        assert "RedactorProtocol" in attrs
        assert "LoggingConfig" in attrs


class TestLoggingAll:
    """Test __all__ exports."""

    def test_all_contains_expected(self) -> None:
        """Test __all__ contains expected items."""
        from quadkit import logging
        assert "get_logger" in logging.__all__
        assert "Logger" in logging.__all__
        assert "LoggerFactoryProtocol" in logging.__all__
        assert "RedactorProtocol" in logging.__all__


class TestLoggingModuleVisibility:
    """Test the logging contracts are part of CoreModule's public surface."""

    def test_core_module_exports_logging_contracts(self) -> None:
        """LoggerFactoryProtocol and RedactorProtocol must be module-visible."""
        from quadkit.app.module import _get_core_exports
        from quadkit.contracts.core.logging import (
            LoggerFactoryProtocol,
            LoggerProtocol,
            RedactorProtocol,
        )

        exports = _get_core_exports()
        assert LoggerProtocol in exports
        assert LoggerFactoryProtocol in exports
        assert RedactorProtocol in exports

    def test_root_package_exports_logging_contracts(self) -> None:
        """The root ``quadkit`` facade exposes the logging contracts."""
        import quadkit

        assert quadkit.LoggerProtocol is not None
        assert quadkit.LoggerFactoryProtocol is not None
        assert quadkit.RedactorProtocol is not None


class TestLoggingInvalidImport:
    """Test that invalid imports raise appropriate errors."""

    def test_invalid_attribute_raises(self) -> None:
        """Test that accessing invalid attribute raises AttributeError."""
        from quadkit import logging
        with pytest.raises(AttributeError):
            _ = logging.nonexistent_attribute
