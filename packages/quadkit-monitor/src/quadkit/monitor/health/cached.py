from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.data import DatabaseProviderProtocol
from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.logging import get_logger
from quadkit.monitor.health.sanitize import safe_error_message

logger = get_logger(__name__)


class CachedHealthChecker:
    """Health checker with result caching and background refresh."""

    def __init__(
        self,
        cache_ttl: float = 5.0,
        check_timeout: float = 2.0,
        db_provider: DatabaseProviderProtocol | None = None,
        cache_backend: CacheBackendProtocol | None = None,
    ) -> None:
        self._cache_ttl = cache_ttl
        self._check_timeout = check_timeout
        self._db_provider = db_provider
        self._cache_backend = cache_backend
        self._db_health: HealthCheckResult | None = None
        self._redis_health: HealthCheckResult | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._running = False

    async def start_background_refresh(self) -> None:
        if self._running:
            return
        self._running = True
        create_tracked_task(
            self._refresh_loop(),
            self._background_tasks,
            name="health_refresh_background",
        )

    async def stop_background_refresh(self) -> None:
        self._running = False
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

    async def _refresh_loop(self) -> None:
        while self._running:
            try:
                await asyncio.gather(
                    self._check_database_health(),
                    self._check_redis_health(),
                    return_exceptions=True,
                )
                await asyncio.sleep(self._cache_ttl / 2)
            except Exception:  # noqa: BLE001 — the refresh loop must survive any probe error
                logger.exception("Error in health check refresh")
                await asyncio.sleep(1)

    def _is_cache_valid(self, result: HealthCheckResult | None) -> bool:
        if result is None or result.checked_at is None:
            return False
        age = (datetime.now(UTC) - result.checked_at).total_seconds()
        return age < self._cache_ttl

    async def get_database_health(self) -> HealthCheckResult:
        if not self._is_cache_valid(self._db_health):
            return await self._check_database_health()
        return self._db_health  # type: ignore[return-value]

    async def get_redis_health(self) -> HealthCheckResult:
        if not self._is_cache_valid(self._redis_health):
            return await self._check_redis_health()
        return self._redis_health  # type: ignore[return-value]

    async def _check_database_health(self) -> HealthCheckResult:
        if self._db_provider is None:
            result = HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                checked_at=datetime.now(UTC),
                message="No database provider configured",
            )
            self._db_health = result
            return result

        start = datetime.now(UTC)
        try:
            async with asyncio.timeout(self._check_timeout):
                if hasattr(self._db_provider, "health_check"):
                    health_result = await self._db_provider.health_check()
                    if health_result.get("status") == "healthy":  # type: ignore[attr-defined]
                        latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
                        result = HealthCheckResult(
                            component="database",
                            status=HealthStatus.HEALTHY,
                            checked_at=datetime.now(UTC),
                            duration_ms=latency_ms,
                        )
                    else:
                        latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
                        result = HealthCheckResult(
                            component="database",
                            status=HealthStatus.UNHEALTHY,
                            checked_at=datetime.now(UTC),
                            duration_ms=latency_ms,
                            message=health_result.get(  # type: ignore[attr-defined]
                                "message", "Database health check failed"
                            ),
                        )
                else:
                    if hasattr(self._db_provider, "execute"):
                        await self._db_provider.execute("SELECT 1")
                    elif hasattr(self._db_provider, "execute_query"):
                        await self._db_provider.execute_query("SELECT 1")

                    latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
                    result = HealthCheckResult(
                        component="database",
                        status=HealthStatus.HEALTHY,
                        checked_at=datetime.now(UTC),
                        duration_ms=latency_ms,
                    )
        except Exception as e:  # noqa: BLE001 — any database probe failure is UNHEALTHY, never a raw raise
            logger.warning(
                "database_health_check_failed",
                component="database",
                error=str(e),
            )
            latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
            result = HealthCheckResult(
                component="database",
                status=HealthStatus.UNHEALTHY,
                checked_at=datetime.now(UTC),
                duration_ms=latency_ms,
                message=safe_error_message(e),
            )

        self._db_health = result
        return result

    async def _check_redis_health(self) -> HealthCheckResult:
        if self._cache_backend is None:
            # Mirror the database branch: an absent component is not "healthy".
            result = HealthCheckResult(
                component="redis",
                status=HealthStatus.UNHEALTHY,
                checked_at=datetime.now(UTC),
                message="No cache backend configured",
            )
            self._redis_health = result
            return result

        start = datetime.now(UTC)
        try:
            async with asyncio.timeout(self._check_timeout):
                await self._cache_backend.health_check(timeout=self._check_timeout)

            latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
            result = HealthCheckResult(
                component="redis",
                status=HealthStatus.HEALTHY,
                checked_at=datetime.now(UTC),
                duration_ms=latency_ms,
            )
        except Exception as e:  # noqa: BLE001 — any redis probe failure is UNHEALTHY, never a raw raise
            logger.warning(
                "redis_health_check_failed",
                component="redis",
                error=str(e),
            )
            latency_ms = (datetime.now(UTC) - start).total_seconds() * 1000
            result = HealthCheckResult(
                component="redis",
                status=HealthStatus.UNHEALTHY,
                checked_at=datetime.now(UTC),
                duration_ms=latency_ms,
                message=safe_error_message(e),
            )

        self._redis_health = result
        return result

    async def get_overall_health(self) -> dict[str, Any]:
        db_res = await self.get_database_health()
        redis_res = await self.get_redis_health()

        all_healthy = (db_res.status == HealthStatus.HEALTHY) and (
            redis_res.status == HealthStatus.HEALTHY
        )

        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "components": {"database": db_res.to_dict(), "redis": redis_res.to_dict()},
        }
