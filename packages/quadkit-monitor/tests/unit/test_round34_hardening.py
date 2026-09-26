"""Round 34 hardening pins — driver errors must degrade per the monitor contract.

1. HealthChecker.run_all — a check raising a non-builtin driver error
   reports UNHEALTHY for that component instead of escaping.
2. PrometheusExporter — metric recording failures are swallowed
   (observed as debug logs), never raised into the app.

Run with: pytest tests/unit/test_round34_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quadkit.contracts.core.health import HealthStatus
from quadkit.monitor.backends.exporters.prometheus import PrometheusMetricsExporter
from quadkit.monitor.health.checker import HealthChecker

pytestmark = pytest.mark.unit


class _DriverError(Exception):
    """Stand-in for a driver/SDK error type (not OSError/ConnectionError)."""


class TestHealthCheckerContract:
    @pytest.mark.asyncio
    async def test_driver_error_check_reports_unhealthy(self) -> None:
        checker = HealthChecker()

        async def _bad_check() -> bool:
            raise _DriverError("probe backend down")

        checker.add("probe", _bad_check)

        results = await checker.run_all()

        assert results["probe"].status is HealthStatus.UNHEALTHY


class TestPrometheusExporterSwallows:
    @pytest.mark.asyncio
    async def test_counter_driver_error_does_not_raise(self) -> None:
        exporter = PrometheusMetricsExporter()

        metric = MagicMock()
        metric.labels = MagicMock(side_effect=_DriverError("label store wedged"))
        exporter._metrics["m1"] = metric

        # Must not raise — recording a metric must never break the app.
        await exporter.counter("m1", 1, tags={"a": "b"})
