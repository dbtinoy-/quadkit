"""Round 41 hardening pins — core: health checks never raise.

HealthCoordinator._run_check — when a registered check fails with a
non-builtin driver error type, the coordinator reports UNHEALTHY,
never propagates the raw error (an app's health endpoint must not 500
because one probe is broken).

Run with: pytest tests/unit/test_round41_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core.health import HealthStatus
from quadkit.di.orchestrator.health import HealthCoordinator
from quadkit.di.orchestrator.registry import ProviderRegistry



class _DriverError(Exception):
    """Stand-in for a probe failure (not RuntimeError/OSError/ValueError)."""


class TestHealthCoordinator:
    @pytest.mark.asyncio
    async def test_probe_driver_error_reports_unhealthy(self) -> None:
        coordinator = HealthCoordinator(registry=ProviderRegistry())

        async def _probe(*_args):
            raise _DriverError("probe backend wedged")

        check = MagicMock()
        check.health_check = _probe

        name, result = await coordinator._run_check(
            "flaky-probe", check, None, timeout=1.0
        )

        assert name == "flaky-probe"
        assert result.status == HealthStatus.UNHEALTHY
