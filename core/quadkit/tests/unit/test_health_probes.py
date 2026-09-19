"""Tests for HealthProbeMixin (health/liveness/readiness probes)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from quadkit.app.base import AppState
from quadkit.app.config.models import AppConfig
from quadkit.app.health_probes import HealthProbeMixin
from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)


class _Host(HealthProbeMixin):
    """Minimal host carrying the mixin's owned state."""

    def __init__(self, state: Any, config: Any, orchestrator: Any) -> None:
        self._state = state
        self.name = "probe-host"
        self._config = config
        self._orchestrator = orchestrator


RUNNING = AppState.RUNNING
CREATED = AppState.CREATED


def _host(
    state: AppState = RUNNING,
    *,
    health_check_timeout: float | None = 5.0,
    check_timeout: float = 5.0,
    include_details: bool = True,
    orchestrator: MagicMock | None = None,
) -> _Host:
    config = MagicMock()
    app_cfg = MagicMock(spec=AppConfig)
    app_cfg.health_check_timeout = health_check_timeout
    config.get_section.return_value = app_cfg
    config.health.check_timeout = check_timeout
    config.health.include_details = include_details
    return _Host(state, config, orchestrator or MagicMock())


def _result(status: HealthStatus = HealthStatus.HEALTHY) -> HealthCheckResult:
    return HealthCheckResult(
        component="provider-x",
        status=status,
        message="msg",
        error="boom" if status is HealthStatus.UNHEALTHY else None,
        details={"k": "v"} if status is HealthStatus.UNHEALTHY else None,
    )


class TestEffectiveTimeout:
    def test_explicit_wins(self) -> None:
        assert _host().health_check.__self__._effective_timeout(1.5) == 1.5  # noqa: SLF001

    def test_app_config_next(self) -> None:
        assert _host(health_check_timeout=7.5)._effective_timeout(None) == 7.5  # noqa: SLF001

    def test_health_config_last_resort(self) -> None:
        assert _host(health_check_timeout=None, check_timeout=9.5)._effective_timeout(None) == 9.5  # noqa: SLF001


class TestHealthCheck:
    async def test_not_running_returns_unhealthy(self) -> None:
        host = _host(CREATED)
        result = await host.health_check()
        assert len(result.components) == 1
        assert result.components[0].status is HealthStatus.UNHEALTHY
        assert "created" in result.components[0].message

    async def test_running_aggregates_orchestrator(self) -> None:
        orch = MagicMock()
        orch.health_check = AsyncMock(
            return_value={"p1": _result(), "p2": _result()}
        )
        host = _host(orchestrator=orch)
        result = await host.health_check(timeout=2.5)
        assert len(result.components) == 2
        orch.health_check.assert_awaited_once_with(2.5)

    async def test_details_scrubbed_when_disabled(self) -> None:
        orch = MagicMock()
        orch.health_check = AsyncMock(
            return_value={"p1": _result(HealthStatus.UNHEALTHY)}
        )
        host = _host(orchestrator=orch, include_details=False)
        result = await host.health_check()
        comp = result.components[0]
        assert comp.status is HealthStatus.UNHEALTHY
        assert comp.message is None
        assert comp.error is None
        assert comp.details is None

    async def test_details_kept_when_enabled(self) -> None:
        orch = MagicMock()
        orch.health_check = AsyncMock(
            return_value={"p1": _result(HealthStatus.UNHEALTHY)}
        )
        host = _host(orchestrator=orch, include_details=True)
        result = await host.health_check()
        comp = result.components[0]
        assert comp.message == "msg"
        assert comp.error == "boom"


class TestLivenessReadiness:
    async def test_liveness_not_running(self) -> None:
        host = _host(CREATED)
        result = await host.liveness()
        assert result.components[0].category is HealthCheckCategory.LIVENESS
        assert result.components[0].status is HealthStatus.UNHEALTHY

    async def test_liveness_running(self) -> None:
        orch = MagicMock()
        expected = AggregateHealthResult(components=[_result()])
        orch.run_liveness = AsyncMock(return_value=expected)
        host = _host(orchestrator=orch)
        result = await host.liveness(timeout=3.0)
        assert result is expected
        orch.run_liveness.assert_awaited_once_with(3.0)

    async def test_readiness_not_running(self) -> None:
        host = _host(CREATED)
        result = await host.readiness()
        assert result.components[0].category is HealthCheckCategory.READINESS

    async def test_readiness_running(self) -> None:
        orch = MagicMock()
        expected = AggregateHealthResult(components=[_result()])
        orch.run_readiness = AsyncMock(return_value=expected)
        host = _host(orchestrator=orch)
        result = await host.readiness()
        assert result is expected

    async def test_liveness_scrubs_details_when_disabled(self) -> None:
        raw = _result(HealthStatus.UNHEALTHY)
        expected = AggregateHealthResult(components=[raw])
        orch = MagicMock()
        orch.run_liveness = AsyncMock(return_value=expected)
        host = _host(orchestrator=orch, include_details=False)
        result = await host.liveness()
        assert result.components[0].message is None


class TestProbeUnavailableResult:
    def test_category_and_state_message(self) -> None:
        host = _host(CREATED)
        result = host._probe_unavailable_result(HealthCheckCategory.STARTUP)  # noqa: SLF001
        comp = result.components[0]
        assert comp.component == "probe-host"
        assert comp.category is HealthCheckCategory.STARTUP
        assert comp.status is HealthStatus.UNHEALTHY
        assert "created" in comp.message
