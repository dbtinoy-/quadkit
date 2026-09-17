"""Resource unit contracts for per-tenant resource quotas (LXF-001)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from quadkit.contracts.ai.governance.errors import GovernanceError


class ResourceWindowKind(str, Enum):
    """Time window strategy for resource tracking."""

    SLIDING = "sliding"
    CALENDAR = "calendar"
    INSTANTANEOUS = "instantaneous"


@dataclass(frozen=True, slots=True)
class ResourceUnit:
    """A measurable resource the governance system tracks per tenant."""

    name: str
    unit_kind: str
    window: timedelta | None = None
    window_kind: ResourceWindowKind = ResourceWindowKind.SLIDING


@dataclass(frozen=True, slots=True)
class ResourceQuota:
    """Per-tenant quota for a specific resource unit."""

    tenant_id: str
    unit: ResourceUnit
    limit: float
    soft_threshold_pct: float | None = None


@dataclass(frozen=True, slots=True)
class ResourceUsageSnapshot:
    """A point-in-time snapshot of resource usage."""

    tenant_id: str
    unit_name: str
    current: float
    limit: float
    window_resets_at: datetime | None = None


class ResourceUsageResult(str, Enum):
    """Result of a resource usage check."""

    APPROVED = "approved"
    SOFT_THRESHOLD_BREACH = "soft_threshold_breach"
    EXHAUSTED = "exhausted"


class ResourceExhaustedError(GovernanceError):
    """Raised when a resource quota is exhausted."""

    _code: str = "QK_ERR_GOV_010"

    def __init__(
        self,
        tenant_id: str,
        unit_name: str,
        limit: float,
        current: float,
        actor_id: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.unit_name = unit_name
        self.limit = limit
        self.current = current
        self.actor_id = actor_id
        super().__init__(
            f"Resource quota exhausted: tenant={tenant_id}, unit={unit_name}, "
            f"{current}/{limit}"
        )


__all__ = [
    "ResourceExhaustedError",
    "ResourceQuota",
    "ResourceUnit",
    "ResourceUsageResult",
    "ResourceUsageSnapshot",
    "ResourceWindowKind",
]
