"""Baseline health probes for a running application.

A running application owns one truthful signal no provider can speak
for: the process is live, started, and able to serve.  Probe categories
aggregate whatever checks register; the baseline seed keeps an empty
pool from masquerading as ``UNKNOWN`` while registered checks still
gate the aggregate.
"""

from quadkit import Application, Provider
from quadkit.contracts.core.di import ContainerRegistrarProtocol
from quadkit.contracts.core.health import (
    HealthCheckCategory,
    HealthCheckProtocol,
    HealthCheckResult,
    HealthStatus,
)


async def test_stock_app_reports_baseline_probes() -> None:
    async with Application.boot() as app:
        for probe, category in (
            (app.liveness, HealthCheckCategory.LIVENESS),
            (app.readiness, HealthCheckCategory.READINESS),
            (app.startup_check, HealthCheckCategory.STARTUP),
        ):
            result = await probe()
            assert result.status == HealthStatus.HEALTHY
            assert len(result.components) == 1
            component = result.components[0]
            assert component.component == app.name
            assert component.status == HealthStatus.HEALTHY
            assert component.category == category


class FailingCache(HealthCheckProtocol):
    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="cache",
            status=HealthStatus.UNHEALTHY,
            message="connection refused",
        )


class CacheProvider(Provider):
    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.transient(FailingCache, FailingCache())

    async def health_check(self) -> HealthCheckResult:
        return HealthCheckResult(
            component="cache",
            status=HealthStatus.UNHEALTHY,
            message="connection refused",
        )


async def test_registered_checks_gate_the_aggregate() -> None:
    async with Application.boot(providers=[CacheProvider()]) as app:
        # The provider's unhealthy check lands in the readiness pool;
        # the baseline seed must never mask it.
        result = await app.readiness()
        assert result.status == HealthStatus.UNHEALTHY
        assert {c.component for c in result.components} == {"cache"}


async def test_custom_liveness_check_replaces_the_baseline() -> None:
    async with Application.boot() as app:
        app._orchestrator._health.register(
            "warm-cache",
            FailingCache(),
            category=HealthCheckCategory.LIVENESS,
        )
        result = await app.liveness()
        assert result.status == HealthStatus.UNHEALTHY
        assert {c.component for c in result.components} == {"cache"}


async def test_not_running_probes_begin_unhealthy() -> None:
    app = Application()
    result = await app.liveness()
    assert result.status == HealthStatus.UNHEALTHY
