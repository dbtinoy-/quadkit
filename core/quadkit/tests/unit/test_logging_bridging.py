"""Stdlib bridge, configure, getLogger, per-level tests."""

from __future__ import annotations

import pytest
import structlog

from quadkit.logging import apply_config, configure_logging, get_logger, reset_logging
from quadkit.logging.config import LoggingConfig, RedactionConfig, SamplingConfig

# ---------------------------------------------------------------------------
# Stdlib bridge
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_stdlib_handlers() -> None:
    """Remove handlers added by TestStdlibBridge to avoid cross-test pollution."""
    yield
    reset_logging()



class TestStdlibBridge:
    """Test that stdlib logging is bridged into structlog's pipeline."""

    def test_stdlib_logger_output_after_configure_logging(self, capsys: pytest.CaptureFixture[str]) -> None:
        """After configure_logging, stdlib loggers write structured output."""
        import logging

        configure_logging(level="DEBUG", json_format=True)

        stdlib_logger = logging.getLogger("test_stdlib_bridge")
        stdlib_logger.info("bridge test message")

        captured = capsys.readouterr()
        assert "bridge test message" in captured.out + captured.err

    def test_stdlib_logger_respects_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Stdlib handler respects the configured log level."""
        import logging

        configure_logging(level="WARNING", json_format=True)

        stdlib_logger = logging.getLogger("test_stdlib_level")
        stdlib_logger.info("should not appear")
        stdlib_logger.warning("should appear")

        captured = capsys.readouterr()
        outerr = captured.out + captured.err
        assert "should not appear" not in outerr
        assert "should appear" in outerr

# ---------------------------------------------------------------------------
# Basic configure_logging
# ---------------------------------------------------------------------------


class TestConfigureLogging:
    """Test core configure_logging() functionality."""

    def test_default_configuration(self) -> None:
        """configure_logging() runs without errors using defaults."""
        configure_logging()

    def test_json_format(self) -> None:
        """configure_logging(json_format=True) configures JSON renderer."""
        configure_logging(json_format=True)
        # Verify structlog config has JSONRenderer
        cfg = structlog.get_config()
        renderer_types = [type(p).__name__ for p in cfg["processors"]]
        assert "JSONRenderer" in renderer_types

    def test_console_format(self) -> None:
        """configure_logging(json_format=False) configures ConsoleRenderer."""
        configure_logging(json_format=False)
        cfg = structlog.get_config()
        renderer_types = [type(p).__name__ for p in cfg["processors"]]
        assert "ConsoleRenderer" in renderer_types

    def test_level_setting(self) -> None:
        """Global level is applied to the wrapper class."""
        configure_logging(level="DEBUG")
        # Should not raise — just verify it completes
        configure_logging(level="ERROR")


class TestServiceName:
    """Test that service_name is injected into the pipeline."""

    def test_service_name_injected(self, capsys: pytest.CaptureFixture[str]) -> None:
        """configure_logging(service_name=...) adds a service field."""
        configure_logging(level="DEBUG", json_format=True, service_name="my-app")
        logger = get_logger()
        logger.info("service_event", value=1)
        captured = capsys.readouterr()
        outerr = captured.out + captured.err
        assert "my-app" in outerr

    def test_explicit_service_binding_wins(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A caller-supplied service override is not clobbered."""
        configure_logging(level="DEBUG", json_format=True, service_name="my-app")
        logger = get_logger().bind(service="override")
        logger.info("service_event", value=1)
        captured = capsys.readouterr()
        outerr = captured.out + captured.err
        assert "override" in outerr
        assert "my-app" not in outerr


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------


class TestGetLogger:
    """Test get_logger() behavior and .name attribute."""

    def test_default_logger_name(self) -> None:
        """get_logger(None) returns a logger with name 'quadkit'."""
        logger = get_logger()
        assert hasattr(logger, "name")
        assert logger.name == "quadkit"

    def test_auto_prefix(self) -> None:
        """get_logger('mymodule') prepends 'quadkit.' prefix."""
        logger = get_logger("mymodule")
        assert logger.name == "quadkit.mymodule"

    def test_no_double_prefix(self) -> None:
        """get_logger('quadkit.di') does not double-prefix."""
        logger = get_logger("quadkit.di")
        assert logger.name == "quadkit.di"

    def test_logger_has_standard_methods(self) -> None:
        """Logger exposes standard log methods."""
        logger = get_logger("test")
        for method in ("debug", "info", "warning", "error"):
            assert hasattr(logger, method), f"Logger missing '{method}' method"


# ---------------------------------------------------------------------------
# Per-logger level overrides
# ---------------------------------------------------------------------------


class TestPerLoggerLevels:
    """Test per-logger level filtering via _level_filter_processor."""

    def test_levels_parameter_accepted(self) -> None:
        """configure_logging() accepts 'levels' parameter."""
        configure_logging(
            level="INFO",
            levels={"quadkit.di": "DEBUG", "quadkit.web": "WARNING"},
        )

    def test_level_filter_drops_below_threshold(self) -> None:
        """Events below per-logger level are dropped."""
        from quadkit.logging.processors import _level_filter_processor

        configure_logging(
            level="DEBUG",  # global allows DEBUG
            levels={"quadkit.noisy": "WARNING"},  # but noisy module is WARNING
        )

        event_dict = {"event": "test", "logger": "quadkit.noisy"}
        # DEBUG event for a WARNING-level logger should be dropped
        with pytest.raises(structlog.DropEvent):
            _level_filter_processor(None, "debug", event_dict)

    def test_level_filter_passes_above_threshold(self) -> None:
        """Events at or above per-logger level pass through."""
        from quadkit.logging.processors import _level_filter_processor

        configure_logging(
            level="DEBUG",
            levels={"quadkit.noisy": "WARNING"},
        )

        event_dict = {"event": "test", "logger": "quadkit.noisy"}
        result = _level_filter_processor(None, "error", event_dict)
        assert result is event_dict

    def test_level_filter_ignores_unconfigured_loggers(self) -> None:
        """Loggers without per-logger overrides are not filtered."""
        from quadkit.logging.processors import _level_filter_processor

        configure_logging(
            level="DEBUG",
            levels={"quadkit.noisy": "WARNING"},
        )

        event_dict = {"event": "test", "logger": "quadkit.other"}
        result = _level_filter_processor(None, "debug", event_dict)
        assert result is event_dict

    def test_level_filter_matches_prefix(self) -> None:
        """Per-logger level matches logger name prefixes."""
        from quadkit.logging.processors import _level_filter_processor

        configure_logging(
            level="DEBUG",
            levels={"quadkit.di": "ERROR"},
        )

        # Sub-logger should inherit the prefix rule
        event_dict = {"event": "test", "logger": "quadkit.di.container"}
        with pytest.raises(structlog.DropEvent):
            _level_filter_processor(None, "warning", event_dict)

    def test_no_levels_means_no_filtering(self) -> None:
        """When no levels are configured, processor is a no-op."""
        from quadkit.logging.processors import _level_filter_processor

        configure_logging(level="DEBUG")  # no levels param

        event_dict = {"event": "test", "logger": "quadkit.anything"}
        result = _level_filter_processor(None, "debug", event_dict)
        assert result is event_dict


# ---------------------------------------------------------------------------
# Log sampling
# ---------------------------------------------------------------------------


