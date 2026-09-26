"""Tests for version-skew config field."""

from __future__ import annotations

from quadkit.events.config import EventsConfig


class TestVersionSkewConfig:
    def test_default_is_enabled(self) -> None:
        cfg = EventsConfig()
        assert cfg.version_skew_alerts_enabled is True

    def test_can_disable(self) -> None:
        cfg = EventsConfig(version_skew_alerts_enabled=False)
        assert cfg.version_skew_alerts_enabled is False
