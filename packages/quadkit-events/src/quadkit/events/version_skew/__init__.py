"""Event version-skew alerting subsystem."""

from __future__ import annotations

from quadkit.events.version_skew.decorator import known_events
from quadkit.events.version_skew.registry import KnownEventSetRegistry
from quadkit.events.version_skew.subscription import VersionAwareSubscription

__all__ = [
    "KnownEventSetRegistry",
    "VersionAwareSubscription",
    "known_events",
]
