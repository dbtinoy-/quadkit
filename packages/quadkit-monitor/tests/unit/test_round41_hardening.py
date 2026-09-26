"""Round 41 hardening pins — quadkit-monitor: optional DB exporter wiring.

_MonitorLifecycleMixin.boot — when resolving the optional
DatabaseProviderProtocol for the DB-backed metrics exporter fails with
a non-KeyError error type (unregistered containers raise
UnresolvableDependencyError; driver failures raise driver errors),
boot degrades (no exporter) instead of raising.

Run with: pytest tests/unit/test_round41_hardening.py -v
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.monitor.di._lifecycle import _MonitorLifecycleMixin

pytestmark = pytest.mark.unit


class _DriverError(Exception):
    """Stand-in for a container/driver error (not KeyError)."""


class TestBootDbExporterWiring:
    @pytest.mark.asyncio
    async def test_boot_degrades_when_db_provider_resolution_fails(self) -> None:
        provider = _MonitorLifecycleMixin.__new__(_MonitorLifecycleMixin)

        backend = MagicMock()
        backend.initialize = AsyncMock()
        backend.tracer = None
        provider.backend = backend
        provider.metrics_collector = MagicMock()
        provider.metrics_exporter = None
        provider._config = SimpleNamespace(
            error_tracking=None,
            prometheus=SimpleNamespace(store_in_db=True, metrics_table="m"),
            slo=None,
        )

        async def _resolve(what: object) -> object:
            if what is DatabaseProviderProtocol:
                raise _DriverError("db provider wedged")
            return None

        container = MagicMock()
        container.resolve = _resolve
        container.resolve_optional = AsyncMock(return_value=None)
        container.singleton = MagicMock()

        # Must not raise — the DB exporter is optional.
        await provider.boot(container)

        assert provider.metrics_exporter is None
