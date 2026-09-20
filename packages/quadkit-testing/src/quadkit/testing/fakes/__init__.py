"""Fake implementations for testing."""

from __future__ import annotations

from typing import Any, Final

from quadkit.testing._lazy_exports import resolve_export
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

_LAZY_IMPORTS: Final[dict[str, tuple[str, str]]] = {
    "FakeRotatableSecretStore": (
        "quadkit.testing.fakes.secrets",
        "FakeRotatableSecretStore",
    ),
}

# Re-exports the production memory backend owned by ``the optional provider``, which
# is not part of the published set.
_OPTIONAL_MODULES: Final[frozenset[str]] = frozenset({"quadkit.testing.fakes.secrets"})


def __getattr__(name: str) -> Any:
    """Import and return a public attribute on first access."""
    return resolve_export(
        name,
        _LAZY_IMPORTS,
        package=__name__,
        optional=_OPTIONAL_MODULES,
    )


def __dir__() -> list[str]:
    """Return the importable public names."""
    return sorted(__all__)


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
