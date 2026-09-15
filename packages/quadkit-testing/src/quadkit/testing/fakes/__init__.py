"""Fake implementations for testing."""

from __future__ import annotations

from quadkit.testing.fakes.audit import FakeAuditLogger
from quadkit.testing.fakes.buses import FakeCommandBus, FakeQueryBus
from quadkit.testing.fakes.cache import FakeCache, FakeStateStore
from quadkit.testing.fakes.clock import Clock, FakeClock, SystemClock
from quadkit.testing.fakes.config import FakeConfig
from quadkit.testing.fakes.events import FakeEventBus
from quadkit.testing.fakes.governance import FakeResourceUnitTracker
from quadkit.testing.fakes.lifecycle import FakeUnitOfWork
from quadkit.testing.fakes.logging import FakeLogger, LogEntry
from quadkit.testing.fakes.monitoring import FakeMetricsCollector
from quadkit.testing.fakes.redis import FakeRedisClient
from quadkit.testing.fakes.tracing import FakeSpan, FakeTracer

# Optional: re-exports the production memory backend owned by
# ``quadkit-secrets``, which is not part of the published set.
try:
    from quadkit.testing.fakes.secrets import FakeRotatableSecretStore
except ImportError:  # pragma: no cover - depends on optional extra
    pass

__all__ = [
    "Clock",
    "FakeAuditLogger",
    "FakeCache",
    "FakeClock",
    "FakeCommandBus",
    "FakeConfig",
    "FakeEventBus",
    "FakeLogger",
    "FakeMetricsCollector",
    "FakeQueryBus",
    "FakeRedisClient",
    "FakeResourceUnitTracker",
    "FakeRotatableSecretStore",
    "FakeSpan",
    "FakeStateStore",
    "FakeTracer",
    "FakeUnitOfWork",
    "LogEntry",
    "SystemClock",
]
