"""Protocol-based database and cache readiness provider for QuadKit Monitor."""

from __future__ import annotations

from quadkit.contracts.core import HealthCheckCategory, HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import ContainerResolverProtocol
from quadkit.contracts.data.sql import DatabaseProviderProtocol
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.contracts.observability.metrics import HealthCheckRegistryProtocol
from quadkit.di.provider import Provider
from quadkit.logging import get_logger
from quadkit.monitor.health.registry import HealthCheckRegistry

logger = get_logger(__name__)


class InfrastructureHealthProvider(Provider):
    """Register database and cache readiness probes via Tier-0 protocols."""

    name = "infra:health"

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Register ``infra:db`` and ``infra:cache`` readiness checks."""
        try:
            registry: HealthCheckRegistryProtocol = await container.resolve(
                HealthCheckRegistryProtocol
            )
        except Exception:  # noqa: BLE001 — fallback when concrete registry was bound directly
            registry = await container.resolve(HealthCheckRegistry)

        async def _db_readiness() -> HealthCheckResult:
            try:
                db_provider = await container.resolve(DatabaseProviderProtocol)
                result = await db_provider.health_check()
                return HealthCheckResult(
                    component="infra:db",
                    status=result.status,
                    message=result.message or "Database connection checked",
                    details=result.details,
                    error=result.error,
                )
            except TimeoutError:
                return HealthCheckResult(
                    component="infra:db",
                    status=HealthStatus.DEGRADED,
                    message="Database connection timeout",
                    error="timeout",
                )
            except Exception as exc:  # noqa: BLE001 — probe reports UNHEALTHY
                return HealthCheckResult(
                    component="infra:db",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database connection failed: {exc!s}",
                    error=type(exc).__name__,
                )

        async def _cache_readiness() -> HealthCheckResult:
            try:
                cache_backend = await container.resolve(CacheBackendProtocol)
                test_key = "__health_check_test__"
                test_value = "ok"
                await cache_backend.set(test_key, test_value, ttl=1)
                raw = await cache_backend.get(test_key)
                value = (
                    raw.unwrap()
                    if hasattr(raw, "is_ok") and raw.is_ok()
                    else (None if hasattr(raw, "is_ok") else raw)
                )
                if value == test_value:
                    await cache_backend.delete(test_key)
                    return HealthCheckResult(
                        component="infra:cache",
                        status=HealthStatus.HEALTHY,
                        message="Cache connection healthy",
                    )
                return HealthCheckResult(
                    component="infra:cache",
                    status=HealthStatus.UNHEALTHY,
                    message="Cache set/get verification failed",
                    error="verification_failed",
                )
            except TimeoutError:
                return HealthCheckResult(
                    component="infra:cache",
                    status=HealthStatus.DEGRADED,
                    message="Cache connection timeout",
                    error="timeout",
                )
            except (RuntimeError, ValueError, OSError, TypeError) as exc:
                return HealthCheckResult(
                    component="infra:cache",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Cache connection failed: {exc!s}",
                    error=type(exc).__name__,
                )

        registry.add(
            "infra:db",
            _db_readiness,
            category=HealthCheckCategory.READINESS,
        )
        registry.add(
            "infra:cache",
            _cache_readiness,
            category=HealthCheckCategory.READINESS,
        )
        logger.info("infrastructure_health_checks_registered", module=self.name)


__all__ = ["InfrastructureHealthProvider"]
