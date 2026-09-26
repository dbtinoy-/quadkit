from __future__ import annotations

from collections.abc import Callable

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.monitor.health.base import HealthCheck


class FunctionHealthCheck(HealthCheck):
    """Health check implemented as a function."""

    def __init__(self, name: str, func: Callable, critical: bool = True):
        super().__init__(name, critical)
        self.func = func

    async def check(self) -> HealthCheckResult:
        result = await self.func()

        if isinstance(result, tuple):
            status, message = result
            return HealthCheckResult(
                component=self.name, status=status, message=message
            )
        if isinstance(result, HealthStatus):
            return HealthCheckResult(component=self.name, status=result)
        if isinstance(result, HealthCheckResult):
            return result
        status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
        return HealthCheckResult(component=self.name, status=status)
