from __future__ import annotations

from abc import ABC, abstractmethod

from quadkit.contracts.core import HealthCheckResult


class HealthCheck(ABC):
    """Base class for health checks."""

    def __init__(self, name: str, critical: bool = True, timeout: float | None = None):
        """Initialize the check.

        Args:
            name: Registered check name.
            critical: Whether an unhealthy result fails readiness.
            timeout: Optional per-check seconds bound. Enforced by
                :meth:`HealthCheckRegistry.run_all` and friends; ``None``
                leaves the check unbounded.
        """
        self.name = name
        self.critical = critical
        self.timeout = timeout

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        pass
