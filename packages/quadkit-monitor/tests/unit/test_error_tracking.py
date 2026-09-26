"""Tests for optional error tracking integration in Quadkit Monitor."""

from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace

from quadkit.monitor.config import ErrorTrackingConfig
from quadkit.monitor.error_tracking import (
    ErrorTrackerProtocol,
    NullErrorTracker,
    SentryErrorTracker,
    setup_error_tracking,
)
from quadkit.validation import SecretStr


class TestSetupErrorTracking:
    def test_noop_when_dsn_unset(self):
        """No DSN means a no-op tracker and no external dependency."""
        tracker = setup_error_tracking(ErrorTrackingConfig())

        assert isinstance(tracker, NullErrorTracker)
        tracker.capture_exception(RuntimeError("boom"))
        tracker.flush()

    def test_noop_when_dsn_blank(self):
        """A blank DSN is treated the same as an unset one."""
        tracker = setup_error_tracking(ErrorTrackingConfig(dsn=" "))

        assert isinstance(tracker, NullErrorTracker)

    def test_dsn_without_sentry_falls_back_to_noop(self):
        """Missing sentry-sdk degrades gracefully when a DSN is set."""
        if importlib.util.find_spec("sentry_sdk") is not None:
            return  # covered by the with-sentry test in the CI env

        tracker = setup_error_tracking(
            ErrorTrackingConfig(dsn="https://public@sentry.io/1")
        )

        assert isinstance(tracker, NullErrorTracker)

    def test_dsn_with_sentry_builds_sentry_tracker(self, monkeypatch):
        """A DSN plus an installed sentry-sdk produces a Sentry tracker."""
        fake_sentry = SimpleNamespace(
            init=lambda **kwargs: None,
            capture_exception=lambda exc: None,
            flush=lambda timeout=2.0: True,
        )
        monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)

        tracker = setup_error_tracking(
            ErrorTrackingConfig(dsn="https://public@sentry.io/1")
        )

        assert isinstance(tracker, SentryErrorTracker)
        assert isinstance(tracker, ErrorTrackerProtocol)
        tracker.capture_exception(ValueError("bad"))
        tracker.flush()

    def test_config_env_loading(self, tmp_path, monkeypatch):
        """QK_MONITOR__ERROR_TRACKING__DSN populates MonitorConfig."""
        from quadkit.monitor.config import MonitorConfig

        monkeypatch.setenv("QK_MONITOR__ERROR_TRACKING__DSN", "https://a@b/1")
        monkeypatch.setenv("QK_MONITOR__ERROR_TRACKING__ENVIRONMENT", "staging")

        config = MonitorConfig.from_yaml(tmp_path / "application.yaml")

        dsn = config.error_tracking.dsn
        assert (
            dsn.get_secret_value() if hasattr(dsn, "get_secret_value") else dsn
        ) == "https://a@b/1"
        assert config.error_tracking.environment == "staging"


class TestSentryErrorTracker:
    def test_init_passes_config_to_sentry(self):
        """Sentry init receives the configured DSN and options."""
        calls: dict = {}
        fake_sentry = SimpleNamespace(init=lambda **kwargs: calls.update(kwargs))

        SentryErrorTracker(
            ErrorTrackingConfig(
                dsn=SecretStr("https://a@b/1"),
                environment="production",
                traces_sample_rate=0.5,
                send_default_pii=True,
            ),
            fake_sentry,
        )

        assert calls["dsn"] == "https://a@b/1"
        assert calls["environment"] == "production"
        assert calls["traces_sample_rate"] == 0.5
        assert calls["send_default_pii"] is True
