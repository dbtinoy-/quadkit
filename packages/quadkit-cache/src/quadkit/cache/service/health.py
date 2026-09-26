"""Health and metrics helpers for the Quadkit cache provider.

These module-level functions are extracted from
:class:`~quadkit.cache.di.provider.CacheProvider` so that ``provider.py``
stays focused on lifecycle management.  They are called by the provider and
are not part of the public API surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.cache.service.core import CacheService
    from quadkit.cache.service.stampede import StampedeProtectedCache
    from quadkit.contracts import CacheBackendProtocol

logger = get_logger(__name__)


def _health_details(value: Any) -> Any:
    """Convert framework health results into JSON-safe detail payloads.

    ``HealthCheckResult`` is a dataclass, rather than a Pydantic model, so
    returning it directly from a provider detail tree eventually makes a web
    health response fail during JSON encoding.  Prefer its explicit public
    serializer, then support Pydantic-like results and plain mappings used by
    third-party backends.
    """
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    return value


async def get_health_status(
    services: dict[str, CacheService],
    backends: dict[str, CacheBackendProtocol],
) -> HealthCheckResult:
    """Aggregate health across all cache services and backends.

    Args:
        services: Mapping of backend name → CacheService instance.
        backends: Mapping of backend name → CacheBackendProtocol instance.

    Returns:
        Structured :class:`~quadkit.contracts.types.HealthCheckResult` with
        per-service and per-backend detail.
    """
    overall_status = HealthStatus.HEALTHY
    details: dict[str, Any] = {"services": {}, "backends": {}}
    errors: list[str] = []

    # --- Services ---
    for name, service in services.items():
        try:
            try:
                service_status = await service.health_check()
            except TypeError:
                service_status = service.health_check()  # type: ignore[assignment]

            if service_status is not None and hasattr(service_status, "status"):
                status_value = service_status.status
                error_value = getattr(service_status, "error", None)
                if status_value != HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
                    if error_value:
                        errors.append(f"Service {name}: {error_value}")
                service_dict = _health_details(service_status)
            elif isinstance(service_status, dict):
                status_value = service_status.get("status", "unknown")
                error_value = service_status.get("error")
                if status_value != "healthy":
                    overall_status = HealthStatus.DEGRADED
                    if error_value:
                        errors.append(f"Service {name}: {error_value}")
                service_dict = service_status
            else:
                service_dict = {
                    "status": "unknown",
                    "error": "Invalid health check result",
                }

            details["services"][name] = service_dict
        except Exception as e:  # noqa: BLE001 — a backend health-check failure degrades the status, never raises
            details["services"][name] = {"status": "unhealthy", "error": str(e)}
            overall_status = HealthStatus.UNHEALTHY
            errors.append(f"Service {name} check failed: {e}")

    # --- Backends ---
    for name, backend in backends.items():
        try:
            try:
                backend_status = await backend.health_check()
            except TypeError:
                backend_status = backend.health_check()  # type: ignore[assignment]

            if backend_status is not None and hasattr(backend_status, "status"):
                status_value = backend_status.status
                if status_value != HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED
                backend_dict = _health_details(backend_status)
            elif isinstance(backend_status, dict):
                status_value = backend_status.get("status", "unknown")
                if status_value != "healthy":
                    overall_status = HealthStatus.DEGRADED
                backend_dict = backend_status
            else:
                backend_dict = {"status": "unknown"}

            details["backends"][name] = backend_dict

        except Exception as e:  # noqa: BLE001 — a backend health-check failure degrades the status, never raises
            details["backends"][name] = {"status": "unhealthy", "error": str(e)}
            overall_status = HealthStatus.UNHEALTHY
            errors.append(f"Backend {name} check failed: {e}")

    return HealthCheckResult(
        component="cache:provider",
        status=overall_status,
        details=details,
        error=" | ".join(errors) if errors else None,
    )


async def get_metrics(
    services: dict[str, CacheService],
    backends: dict[str, CacheBackendProtocol],
    protection: StampedeProtectedCache | None,
) -> dict[str, Any]:
    """Collect metrics from all registered cache services.

    Args:
        services: Mapping of backend name → CacheService instance.
        backends: Mapping of backend name → CacheBackendProtocol instance.
        protection: Stampede protection instance, or ``None`` when disabled.

    Returns:
        Metrics dictionary with per-provider summary and per-service stats.
    """
    metrics: dict[str, Any] = {
        "provider": {
            "services_count": len(services),
            "backends_count": len(backends),
            "protection_enabled": protection is not None,
        },
        "services": {},
    }

    for name, service in services.items():
        try:
            service_metrics = service.get_metrics()
            metrics["services"][name] = service_metrics
        except Exception as e:  # noqa: BLE001 — one bad service must not break metrics aggregation
            metrics["services"][name] = {"error": str(e)}

    return metrics


__all__ = ["get_health_status", "get_metrics"]
