"""Unit tests for ``quadkit.web.HealthController``."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.serialization import loads
from quadkit.web import HealthController


class _RegistryStub:
    def __init__(self, status: Any) -> None:
        self._status = status

    def add(self, name: str, check: Any, **kwargs: Any) -> None:
        del name, check, kwargs

    async def run_all(self) -> tuple[Any, dict[str, Any]]:
        return self._status, {"all": "ok"}

    async def run_liveness(self) -> tuple[Any, dict[str, Any]]:
        return self._status, {"live": "ok"}

    async def run_readiness(self) -> tuple[Any, dict[str, Any]]:
        return self._status, {"ready": "ok"}

    async def run_startup(self) -> tuple[Any, dict[str, Any]]:
        return self._status, {"startup": "ok"}


class _ExporterStub:
    content_type = "text/plain; version=0.0.4"

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail

    def export(self) -> str:
        if self._fail:
            raise RuntimeError("scrape failed")
        return "quadkit_up 1\n"


@pytest.mark.asyncio
async def test_health_controller_status_mapping_and_metrics() -> None:
    ok_ctrl = HealthController(_RegistryStub(HealthStatus.HEALTHY), _ExporterStub())
    assert (await ok_ctrl.health_check()).status_code == 200
    assert (await ok_ctrl.readiness()).status_code == 200
    assert (await ok_ctrl.liveness()).status_code == 200
    assert (await ok_ctrl.startup()).status_code == 200

    metrics_resp = await ok_ctrl.metrics()
    assert metrics_resp.status_code == 200
    assert b"quadkit_up 1" in bytes(metrics_resp.body)

    down_ctrl = HealthController(
        _RegistryStub(HealthStatus.UNHEALTHY),
        _ExporterStub(fail=True),
    )
    ready_resp = await down_ctrl.readiness()
    assert ready_resp.status_code == 503
    assert loads(bytes(ready_resp.body))["status"] == "unhealthy"
    assert (await down_ctrl.metrics()).status_code == 500
