"""Round 41 hardening pins — quadkit-sql: pool probe never raises.

ConnectionPoolMonitor._probe_pool — a pool probe failure with a
non-builtin driver error type (asyncpg/aiomysql exceptions are not
OSError/DatabaseError) triggers eviction and keeps monitoring,
never a raw raise (the method's documented contract).

Run with: pytest tests/unit/test_round41_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.sql.monitoring.database_monitor.pool import ConnectionPoolMonitor


class _DriverError(Exception):
    """Stand-in for a DB driver error type (not OSError/DatabaseError)."""


class _RaisingContext:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def __aenter__(self) -> None:
        raise self._exc

    async def __aexit__(self, *exc_info: object) -> None:
        return None


class TestConnectionPoolMonitorProbe:
    async def test_probe_driver_error_does_not_raise(self) -> None:
        monitor = ConnectionPoolMonitor(collector=MagicMock())

        provider = MagicMock()
        provider.scoped_context = MagicMock(
            return_value=_RaisingContext(_DriverError("driver wedged"))
        )
        provider.evict_dead_connections = AsyncMock(return_value=0)
        monitor._provider = provider

        # Must not raise — monitoring stays resilient.
        await monitor._probe_pool()

        provider.evict_dead_connections.assert_awaited_once()
