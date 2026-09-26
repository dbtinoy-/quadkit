"""Sentry before_send scrubber contract tests.

Follows the package convention for optional ``sentry_sdk``: a fake module is
injected into ``sys.modules`` so the tests run with or without the SDK.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from quadkit.monitor.config import ErrorTrackingConfig
from quadkit.monitor.error_tracking import SentryErrorTracker


@pytest.fixture
def fake_sentry(monkeypatch) -> MagicMock:
    module = MagicMock()
    module.init = MagicMock()
    monkeypatch.setitem(sys.modules, "sentry_sdk", module)
    return module


def _tracker(fake_sentry) -> tuple[SentryErrorTracker, MagicMock]:
    tracker = SentryErrorTracker(
        config=ErrorTrackingConfig(dsn="https://key@sentry.io/1"),
        sentry=fake_sentry,
    )
    return tracker, fake_sentry


def test_init_registers_before_send(fake_sentry):
    _, sentry = _tracker(fake_sentry)
    kwargs = sentry.init.call_args.kwargs
    assert callable(kwargs["before_send"])


def test_scrubber_masks_sensitive_keys_everywhere(fake_sentry):
    _, sentry = _tracker(fake_sentry)
    scrub = sentry.init.call_args.kwargs["before_send"]
    event = {
        "request": {
            "headers": {"Authorization": "Bearer x", "Content-Type": "json"},
            "data": {"password": "hunter2"},
        },
        "extra": {
            "auth_token": "leak",
            "note": "keep me",
        },
    }
    out = scrub(event, {})
    assert out["request"]["headers"]["Authorization"] == "[redacted]"
    assert out["request"]["headers"]["Content-Type"] == "json"
    assert out["request"]["data"]["password"] == "[redacted]"
    assert out["extra"]["auth_token"] == "[redacted]"
    assert out["extra"]["note"] == "keep me"
