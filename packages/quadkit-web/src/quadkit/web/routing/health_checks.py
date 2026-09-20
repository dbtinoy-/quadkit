"""Health checking utilities separated from route handlers.

This module contains the HealthChecker and related Pydantic models. Keeping
this logic here helps keep `health.py` small and focused on HTTP handlers.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, cast

from quadkit.contracts.core import HealthStatus
from quadkit.domain import DomainModel
from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol
    from quadkit.contracts.infra.cache import CacheBackendProtocol

logger = get_logger(__name__)


@dataclass(init=False)
class ComponentHealth(DomainModel):
    status: HealthStatus
    latency_ms: float
    checked_at: datetime
    message: str | None = None


@dataclass(init=False)
class HealthCheckResponse(DomainModel):
    status: HealthStatus
    version: str
    components: dict[str, ComponentHealth]
    checked_at: datetime


class WebHealthChecker:
    """Health checker for web application dependencies.

    Not to be confused with ``quadkit.health.HealthChecker`` from core,
    which is the general-purpose health check aggregator.
    """

    def __init__(
        self,
        *,
        db_provider: DatabaseProviderProtocol | None = None,
        cache_backend: CacheBackendProtocol | None = None,
        app_version: str = "unknown",
    ) -> None:
        self.db_provider = db_provider
        self.cache_backend = cache_backend
        self.app_version = app_version

    async def check_health(self) -> HealthCheckResponse:
        checked_at = ambient_clock.now()

        db_health, redis_health = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
            return_exceptions=True,
        )

        if isinstance(db_health, Exception):
            db_health = ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                message=f"Error: {db_health!s}",
                checked_at=ambient_clock.now(),
            )

        if isinstance(redis_health, Exception):
            redis_health = ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                message=f"Error: {redis_health!s}",
                checked_at=ambient_clock.now(),
            )

        components = {"database": db_health, "redis": redis_health}

        # At runtime exceptions are converted to ComponentHealth instances above.
        # Use typing.cast to inform mypy that this dict contains ComponentHealth values.
        components_typed = cast("dict[str, ComponentHealth]", components)

        overall_status = self._determine_overall_status(components_typed)

        return HealthCheckResponse(
            status=overall_status,
            version=self.app_version,
            components=components_typed,
            checked_at=checked_at,
        )

    async def _check_database(self) -> ComponentHealth:
        if not self.db_provider:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                message="Database provider not configured",
                checked_at=ambient_clock.now(),
            )

        start = ambient_clock.now()

        try:
            # Use the contract's health_check method
            result = await self.db_provider.health_check()

            latency = (ambient_clock.now() - start).total_seconds() * 1000

            # Map HealthCheckResult to ComponentHealth
            if result.status == HealthStatus.HEALTHY:
                status = HealthStatus.HEALTHY
                message = result.message or "Database connection OK"
            elif result.status == HealthStatus.DEGRADED:
                status = HealthStatus.DEGRADED
                message = result.message or "Database degraded"
            else:
                status = HealthStatus.UNHEALTHY
                message = result.message or "Database unhealthy"

            return ComponentHealth(
                status=status,
                latency_ms=latency,
                message=message,
                checked_at=ambient_clock.now(),
            )

        except Exception as exc:  # noqa: BLE001 — health checks must not propagate; any error becomes an UNHEALTHY status
            latency = (ambient_clock.now() - start).total_seconds() * 1000
            logger.exception("Database health check failed")
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(exc),
                checked_at=ambient_clock.now(),
            )

    async def _check_redis(self) -> ComponentHealth:
        if not self.cache_backend:
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                latency_ms=0,
                message="Cache backend not configured",
                checked_at=ambient_clock.now(),
            )

        start = ambient_clock.now()

        try:
            # Use the contract's health_check method
            result = await self.cache_backend.health_check()

            latency = (ambient_clock.now() - start).total_seconds() * 1000

            # Map HealthCheckResult to ComponentHealth
            if result.status == HealthStatus.HEALTHY:
                status = HealthStatus.HEALTHY
                message = result.message or "Cache connection OK"
            elif result.status == HealthStatus.DEGRADED:
                status = HealthStatus.DEGRADED
                message = result.message or "Cache degraded"
            else:
                status = HealthStatus.UNHEALTHY
                message = result.message or "Cache unhealthy"

            return ComponentHealth(
                status=status,
                latency_ms=latency,
                message=message,
                checked_at=ambient_clock.now(),
            )

        except Exception as exc:  # noqa: BLE001 — health checks must not propagate; any error becomes an UNHEALTHY status
            latency = (ambient_clock.now() - start).total_seconds() * 1000
            logger.exception("Cache health check failed")
            return ComponentHealth(
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(exc),
                checked_at=ambient_clock.now(),
            )

    def _determine_overall_status(
        self,
        components: dict[str, ComponentHealth],
    ) -> HealthStatus:
        statuses = [c.status for c in components.values()]

        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        if HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
