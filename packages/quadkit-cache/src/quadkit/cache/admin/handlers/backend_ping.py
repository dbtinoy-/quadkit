"""Backend ping widget handler."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from quadkit.contracts.admin import HealthCheckPayload, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.contracts.core.health import HealthStatus
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol


class BackendPingWidgetHandler:
    """Pings the cache backend.

    Args:
        cache: Injected CacheBackendProtocol.
    """

    def __init__(self, cache: CacheBackendProtocol) -> None:
        self._cache = cache

    async def get_data(
        self, params: WidgetParams
    ) -> Result[HealthCheckPayload, AdminError]:
        """Perform a health check on the cache backend.

        Infrastructure failures (network, timeout) propagate as exceptions.

        Args:
            params: Widget parameters.

        Returns:
            Result containing HealthCheckPayload or AdminError.
        """
        start = time.monotonic()

        # Call health_check if available — infrastructure exceptions propagate
        is_reachable = True
        health_check_method = getattr(self._cache, "health_check", None)
        if health_check_method is not None and callable(health_check_method):
            result = await health_check_method()
            # HealthCheckResult has an is_healthy() method; duck-typed results
            # may expose an is_healthy boolean attribute instead.
            is_healthy = getattr(result, "is_healthy", True)
            is_reachable = is_healthy() if callable(is_healthy) else bool(is_healthy)

        latency_ms = round((time.monotonic() - start) * 1000, 2)
        backend_name = getattr(self._cache, "backend_name", "cache")
        if not isinstance(backend_name, str):
            backend_name = type(self._cache).__name__

        return Ok(
            HealthCheckPayload(
                status=(
                    HealthStatus.HEALTHY if is_reachable else HealthStatus.UNHEALTHY
                ),
                component="cache.backend",
                detail=backend_name,
                latency_ms=latency_ms,
            )
        )


__all__ = ["BackendPingWidgetHandler"]
