"""Health check types for Quadkit Framework."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class HealthCheckCategory(StrEnum):
    """Categorises health checks by their role in the Kubernetes health model.

    Attributes:
        LIVENESS: Checks that the application is alive (not deadlocked).
            Used by ``/health/live`` endpoints.  Failure triggers a restart.
        READINESS: Checks that the application is ready to accept traffic.
            Used by ``/health/ready`` endpoints.  Failure removes the instance
            from the load-balancer rotation.
        STARTUP: Checks that the application has finished its startup sequence.
            Used by ``/health/startup`` endpoints.  Succeeded once; after that
            the probe switches to liveness/readiness.
    """

    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"


class HealthStatus(StrEnum):
    """Unified health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    STARTING = "starting"


@runtime_checkable
class HealthCheckProtocol(Protocol):
    """Protocol for health check capability.

    Expected Behavior:
    - health_check: MUST return a result within a reasonable timeout (~5s).
    - health_check: SHOULD NOT raise exceptions; wrap errors in HealthCheckResult.
    """

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult: ...


@dataclass(frozen=True)
class HealthCheckResult:
    """Result of a health check."""

    component: str
    status: HealthStatus = HealthStatus.HEALTHY
    message: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    details: dict[str, Any] | None = None
    checked_at: datetime | None = None
    category: HealthCheckCategory = HealthCheckCategory.READINESS

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        result: dict[str, Any] = {
            "component": self.component,
            "category": self.category.value,
            "status": str(self.status),
            "duration_ms": round(self.duration_ms, 2),
        }
        if self.message:
            result["message"] = self.message
        if self.error:
            result["error"] = self.error
        if self.details:
            result["details"] = self.details
        if self.checked_at:
            result["checked_at"] = self.checked_at.isoformat()
        return result

    def is_healthy(self) -> bool:
        """Check if status is healthy."""
        return self.status == HealthStatus.HEALTHY

    def is_degraded(self) -> bool:
        """Check if status is degraded."""
        return self.status == HealthStatus.DEGRADED


@dataclass(frozen=True)
class AggregateHealthResult:
    """Composite health result that collects checks from multiple components.

    The aggregate status follows a ``worst-case`` rule:
    * Any ``UNHEALTHY`` check → overall ``UNHEALTHY``
    * Any ``DEGRADED`` check (no UNHEALTHY) → overall ``DEGRADED``
    * All ``HEALTHY`` → overall ``HEALTHY``
    * No checks registered → ``UNKNOWN``
    """

    components: list[HealthCheckResult] = field(default_factory=list)

    @property
    def status(self) -> HealthStatus:
        """Overall status, computed from component checks."""
        if not self.components:
            return HealthStatus.UNKNOWN
        if any(c.status == HealthStatus.UNHEALTHY for c in self.components):
            return HealthStatus.UNHEALTHY
        if any(c.status == HealthStatus.DEGRADED for c in self.components):
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def is_healthy(self) -> bool:
        """Return True only if all components are healthy."""
        return self.status == HealthStatus.HEALTHY

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary suitable for a ``/health`` HTTP response."""
        return {
            "status": self.status.value,
            "components": [c.to_dict() for c in self.components],
        }


@runtime_checkable
class HealthCheckAggregatorProtocol(Protocol):
    """Protocol for services that aggregate health checks from multiple providers.

    Implementations collect :class:`HealthCheckProtocol` instances, run them
    concurrently, and return a single :class:`AggregateHealthResult`.
    """

    def register(
        self,
        name: str,
        check: HealthCheckProtocol,
        *,
        category: HealthCheckCategory = HealthCheckCategory.READINESS,
    ) -> None:
        """Register a named health check.

        Args:
            name: Unique component name for this check.
            check: Object implementing :class:`HealthCheckProtocol`.
            category: Probe category for this check. Defaults to
                :class:`HealthCheckCategory.READINESS`.
        """
        ...

    async def run_all(
        self,
        timeout: float = 5.0,
        *,
        category: HealthCheckCategory | None = None,
    ) -> AggregateHealthResult:
        """Run all registered checks concurrently and aggregate results.

        Args:
            timeout: Per-check timeout in seconds.
            category: Optional probe category filter.

        Returns:
            :class:`AggregateHealthResult` containing all component results.
        """
        ...

    async def run_liveness(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run only liveness checks and aggregate results."""
        ...

    async def run_readiness(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run only readiness checks and aggregate results."""
        ...

    async def run_startup(self, timeout: float = 5.0) -> AggregateHealthResult:
        """Run only startup checks and aggregate results."""
        ...


# Canonical alias — infrastructure protocols should reference this name.
# Identical to HealthCheckProtocol; provided as a mixin-friendly import.
HealthCheckableProtocol = HealthCheckProtocol

__all__ = [
    "AggregateHealthResult",
    "HealthCheckAggregatorProtocol",
    "HealthCheckCategory",
    "HealthCheckProtocol",
    "HealthCheckResult",
    "HealthCheckableProtocol",
    "HealthStatus",
]
