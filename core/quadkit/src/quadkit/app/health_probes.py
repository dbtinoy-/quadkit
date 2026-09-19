"""Health probe surface for :class:`~quadkit.app.base.Application`."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core.health import (
    AggregateHealthResult,
    HealthCheckCategory,
    HealthCheckResult,
    HealthStatus,
)

if TYPE_CHECKING:
    from quadkit.app.base import AppState


class HealthProbeMixin:
    """Aggregate health/liveness/readiness probes over all providers.

    State attributes (``_state``, ``name``, ``_orchestrator``) are owned by
    :class:`~quadkit.app.base.Application`.
    """

    if TYPE_CHECKING:
        _config: Any
        _state: AppState
        name: str
        _orchestrator: Any

    def _effective_timeout(self, timeout: float | None) -> float:
        """Resolve the per-provider health-check timeout.

        Precedence: explicit argument > ``AppConfig.health_check_timeout``
        (``app`` section) > ``HealthConfig.check_timeout`` (``health``
        section, whose default is :data:`DEFAULT_HEALTH_CHECK_TIMEOUT`).
        """
        if timeout is not None:
            return timeout
        from quadkit.app.config.models import AppConfig

        cfg = self._config
        app_config = cfg.get_section("app", AppConfig)
        app_value = app_config.health_check_timeout
        if app_value is not None:
            return float(app_value)
        return float(cfg.health.check_timeout)

    def _apply_details_policy(
        self, result: AggregateHealthResult
    ) -> AggregateHealthResult:
        """Scrub detailed error info when ``HealthConfig.include_details`` is False."""
        if self._config.health.include_details:
            return result
        return AggregateHealthResult(
            components=[
                replace(
                    component,
                    message=None,
                    error=None,
                    details=None,
                )
                for component in result.components
            ]
        )

    async def health_check(self, timeout: float | None = None) -> AggregateHealthResult:
        """Aggregate health check from all providers.

        ``timeout`` (per provider, seconds) falls back to
        ``AppConfig.health_check_timeout`` then ``HealthConfig.check_timeout``.

        Returns an :class:`~quadkit.contracts.core.health.AggregateHealthResult`
        whose ``status`` follows worst-case aggregation across all registered
        provider health checks.
        """
        from quadkit.app.base import AppState  # local: avoid circular import

        timeout = self._effective_timeout(timeout)

        if self._state != AppState.RUNNING:
            return self._apply_details_policy(
                AggregateHealthResult(
                    components=[
                        HealthCheckResult(
                            component=self.name,
                            status=HealthStatus.UNHEALTHY,
                            message=f"Application is {self._state.value}",
                        )
                    ]
                )
            )

        raw: dict[str, Any] = await self._orchestrator.health_check(timeout)
        return self._apply_details_policy(
            AggregateHealthResult(components=list(raw.values()))
        )

    def _baseline_component(
        self,
        result: AggregateHealthResult,
        category: HealthCheckCategory,
    ) -> AggregateHealthResult:
        """Ensure a running application always reports a baseline component.

        Probe categories aggregate whatever checks register against them,
        and an empty pool would otherwise surface as ``UNKNOWN``.  The
        running application itself is the truthful baseline signal: live,
        started, and able to serve.  Registered checks still gate the
        aggregate — seeding only applies when nothing else reported.
        """
        if result.components:
            return result
        return AggregateHealthResult(
            components=[
                HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.HEALTHY,
                    message="application running",
                    category=category,
                )
            ]
        )

    def _probe_unavailable_result(
        self,
        category: HealthCheckCategory,
    ) -> AggregateHealthResult:
        """Build a probe result when the application is not running."""
        return AggregateHealthResult(
            components=[
                HealthCheckResult(
                    component=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Application is {self._state.value}",
                    category=category,
                ),
            ],
        )

    async def liveness(self, timeout: float | None = None) -> AggregateHealthResult:
        """Run liveness checks for the application."""
        from quadkit.app.base import AppState  # local: avoid circular import

        timeout = self._effective_timeout(timeout)
        if self._state != AppState.RUNNING:
            return self._apply_details_policy(
                self._probe_unavailable_result(HealthCheckCategory.LIVENESS)
            )
        live = await self._orchestrator.run_liveness(timeout)
        live = self._baseline_component(live, HealthCheckCategory.LIVENESS)
        return self._apply_details_policy(live)

    async def readiness(self, timeout: float | None = None) -> AggregateHealthResult:
        """Run readiness checks for the application."""
        from quadkit.app.base import AppState  # local: avoid circular import

        timeout = self._effective_timeout(timeout)
        if self._state != AppState.RUNNING:
            return self._apply_details_policy(
                self._probe_unavailable_result(HealthCheckCategory.READINESS)
            )
        ready = await self._orchestrator.run_readiness(timeout)
        ready = self._baseline_component(ready, HealthCheckCategory.READINESS)
        return self._apply_details_policy(ready)


__all__ = ["HealthProbeMixin"]
