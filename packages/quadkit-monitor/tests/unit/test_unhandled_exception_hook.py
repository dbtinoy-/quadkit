"""Tests for the unhandled-exception hook in Quadkit Monitor."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from typing import Any

import structlog

from quadkit.monitor.config import ErrorTrackingConfig
from quadkit.monitor.error_tracking import (
    NullErrorTracker,
    SentryErrorTracker,
    UnhandledExceptionHook,
    install_unhandled_exception_hook,
    setup_error_tracking,
)


class RecordingTracker(NullErrorTracker):
    """NullErrorTracker subclasses allow attachment of additional hooks."""

    def __init__(self) -> None:
        self.captured: list[BaseException] = []

    def capture_exception(self, exc: BaseException) -> None:
        self.captured.append(exc)


class RecordingLogger:
    """Minimal structlog-shaped logger that records event kwargs."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def error(self, event: str, **kwargs: Any) -> None:
        self.events.append({"event": event, **kwargs})


class TestUnhandledExceptionHook:
    def test_captures_exception_to_tracker(self) -> None:
        """The hook forwards every unhandled exception to the tracker."""
        tracker = RecordingTracker()
        logger = RecordingLogger()
        hook = UnhandledExceptionHook(tracker, logger)

        hook(RuntimeError, RuntimeError("boom"), None)

        assert len(tracker.captured) == 1
        assert str(tracker.captured[0]) == "boom"

    def test_logs_event_with_error_type_and_message(self) -> None:
        """The hook emits a structured unhandled_exception event."""
        tracker = RecordingTracker()
        logger = RecordingLogger()
        hook = UnhandledExceptionHook(tracker, logger)

        hook(ValueError, ValueError("bad value"), None)

        assert logger.events == [
            {
                "event": "unhandled_exception",
                "error_type": "ValueError",
                "error_message": "bad value",
            }
        ]

    def test_logs_correlation_id_from_context(self) -> None:
        """Bound trace_id/request_id surface as correlation_id on the log."""
        tracker = RecordingTracker()
        logger = RecordingLogger()
        hook = UnhandledExceptionHook(tracker, logger)

        structlog.contextvars.bind_contextvars(trace_id="trace-123")
        try:
            hook(RuntimeError, RuntimeError("boom"), None)
        finally:
            structlog.contextvars.clear_contextvars()

        assert logger.events[0]["correlation_id"] == "trace-123"
        assert logger.events[0]["trace_id"] == "trace-123"

    def test_prefers_trace_id_then_request_id(self) -> None:
        """trace_id wins over request_id for the correlation id field."""
        tracker = RecordingTracker()
        logger = RecordingLogger()
        hook = UnhandledExceptionHook(tracker, logger)

        structlog.contextvars.bind_contextvars(request_id="req-456", span_id="s")
        try:
            hook(RuntimeError, RuntimeError("boom"), None)
        finally:
            structlog.contextvars.clear_contextvars()

        assert logger.events[0]["correlation_id"] == "req-456"
        assert logger.events[0]["request_id"] == "req-456"
        assert logger.events[0]["span_id"] == "s"

    def test_chains_to_previous_hook(self) -> None:
        """The previously installed hook still receives the exception."""
        previous_calls: list[tuple[Any, Any, Any]] = []
        previous = lambda t, e, tb: previous_calls.append((t, e, tb))  # noqa: E731
        hook = UnhandledExceptionHook(RecordingTracker(), RecordingLogger())
        hook._previous = previous

        hook(RuntimeError, RuntimeError("boom"), None)

        assert len(previous_calls) == 1
        assert previous_calls[0][1].args == ("boom",)

    def test_install_and_uninstall_restore_previous_hook(self) -> None:
        """install() chains and uninstall() restores the prior hook."""
        original = sys.excepthook
        try:
            tracker = RecordingTracker()
            logger = RecordingLogger()
            hook = UnhandledExceptionHook(tracker, logger)

            hook.install()
            assert sys.excepthook is hook
            assert hook._previous is original

            hook.uninstall()
            assert sys.excepthook is original
        finally:
            sys.excepthook = original

    def test_uninstall_does_not_clobber_other_hook(self) -> None:
        """uninstall() leaves a newer, unrelated hook in place."""
        original = sys.excepthook
        try:
            other = lambda *_args: None  # noqa: E731
            hook = UnhandledExceptionHook(RecordingTracker(), RecordingLogger())
            hook.install()
            sys.excepthook = other

            hook.uninstall()
            assert sys.excepthook is other
        finally:
            sys.excepthook = original


class TestInstallUnhandledExceptionHook:
    def test_returns_installed_hook(self) -> None:
        """The helper installs the hook and returns the instance."""
        original = sys.excepthook
        try:
            hook = install_unhandled_exception_hook(
                RecordingTracker(), RecordingLogger()
            )

            assert isinstance(hook, UnhandledExceptionHook)
            assert sys.excepthook is hook
        finally:
            original_hook = sys.excepthook
            hook.uninstall()
            assert sys.excepthook is original
            assert isinstance(original_hook, UnhandledExceptionHook)


class TestSentryDsnFallback:
    def test_env_sentry_dsn_builds_sentry_tracker(self, monkeypatch: Any) -> None:
        """SENTRY_DSN env var enables the Sentry tracker when config is unset."""
        fake_sentry = SimpleNamespace(
            init=lambda **_kwargs: None,
            capture_exception=lambda _exc: None,
            flush=lambda _timeout=2.0: True,
        )
        monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.io/env")

        tracker = setup_error_tracking(ErrorTrackingConfig())

        assert isinstance(tracker, SentryErrorTracker)

    def test_env_sentry_dsn_ignored_when_config_set(self, monkeypatch: Any) -> None:
        """A configured DSN takes precedence over the SENTRY_DSN env var."""
        calls: dict[str, Any] = {}
        fake_sentry = SimpleNamespace(init=lambda **kwargs: calls.update(kwargs))
        monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        monkeypatch.setenv("SENTRY_DSN", "https://public@sentry.io/env")

        tracker = setup_error_tracking(
            ErrorTrackingConfig(dsn="https://public@sentry.io/config")
        )

        assert isinstance(tracker, SentryErrorTracker)
        assert calls["dsn"] == "https://public@sentry.io/config"
