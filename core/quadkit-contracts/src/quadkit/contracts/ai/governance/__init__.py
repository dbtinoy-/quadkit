"""AI governance contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from quadkit.contracts.ai.governance.errors import (
    BudgetExceededError,
    GovernanceError,
    PolicyViolationError,
)
from quadkit.contracts.ai.governance.relay_billing import (
    RelayBillingError,
    RelayBillingProtocol,
    RelayChargeBreakdown,
    RelayPriceEstimatorProtocol,
    RelayUsageRecord,
    RelayUsageReservation,
    RelayUsageScope,
    RelayUsageStoreProtocol,
    billing_store_unavailable,
    charge_overflow,
    duplicate_settlement,
    invalid_usage,
    quota_exhausted,
    reservation_expired,
    unknown_price,
)
from quadkit.contracts.ai.governance.resource_unit import (
    ResourceExhaustedError,
    ResourceQuota,
    ResourceUnit,
    ResourceUsageResult,
    ResourceUsageSnapshot,
    ResourceWindowKind,
)


@dataclass(frozen=True)
class GovernanceDecision:
    """Decision from the governance layer."""

    allowed: bool
    reason: str | None = None
    remaining_budget: float | None = None


@runtime_checkable
class CostTrackingProtocol(Protocol):
    """Protocol for tracking costs."""

    async def track_cost(
        self,
        cost: float,
        model: str,
        user_id: str | None = None,
    ) -> None:
        """Track cost for an operation."""
        ...

    async def get_budget(self, user_id: str | None = None) -> float:
        """Get remaining budget."""
        ...


@runtime_checkable
class AIGovernanceProtocol(Protocol):
    """Protocol for AI Governance and cost tracking."""

    async def check_request(
        self,
        model: str,
        provider: str,
        user_id: str | None = None,
    ) -> GovernanceDecision:
        """Check if request is allowed by governance policies."""
        ...

    async def check_budget(self, cost: float, user_id: str | None = None) -> bool:
        """Check if operation fits within budget."""
        ...

    async def track_cost(
        self,
        cost: float,
        model: str,
        user_id: str | None = None,
    ) -> None:
        """Track cost for an operation."""
        ...


class AuditEventType(StrEnum):
    """Categories of auditable AI operations.

    Shared across the AI governance and observability layers
    via ``quadkit-contracts``.
    """

    CREATED = "created"
    LLM_CALL = "llm_call"
    MODEL_DENIED = "model_denied"
    BUDGET_EXCEEDED = "budget_exceeded"
    RATE_LIMITED = "rate_limited"
    TOOL_CALL = "tool_call"
    AGENT_EXECUTION = "agent_execution"
    SOFT_LIMIT_REACHED = "soft_limit_reached"
    CONFIG_RELOADED = "config_reloaded"


@dataclass(frozen=True)
class AIAuditEvent:
    """Structured representation of an auditable AI operation.

    Concrete data class shared across AI packages via ``quadkit-contracts``.

    Attributes:
        event_type: Category of the operation.
        model: Model identifier (if applicable).
        provider: Provider name (if applicable).
        user_id: User who triggered the operation.
        status: Outcome — ``"allowed"``, ``"denied"``, ``"success"``, ``"error"``.
        tokens: Token count consumed (if applicable).
        cost: Dollar cost incurred (if applicable).
        latency_ms: Request latency in milliseconds (if applicable).
        metadata: Free-form key/value bag for additional context.
        event_id: Unique UUID for the event (auto-generated).
    """

    event_type: AuditEventType
    model: str | None = None
    provider: str | None = None
    user_id: str | None = None
    status: str = "success"
    tokens: int | None = None
    cost: float | None = None
    latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class AIAuditStoreProtocol(Protocol):
    """Protocol for AI audit event persistence backends.

    Implementations must be async and treat ``record()`` as
    fire-and-forget safe — hot-paths must never block on audit persistence.
    """

    async def record(self, event: AIAuditEvent) -> None:
        """Persist a single audit event.

        Args:
            event: The audit event to store.
        """
        ...


__all__ = [
    "AIAuditEvent",
    "AIAuditStoreProtocol",
    "AIGovernanceProtocol",
    "AuditEventType",
    "BudgetExceededError",
    "CostTrackingProtocol",
    "GovernanceDecision",
    "GovernanceError",
    "PolicyViolationError",
    "RelayBillingError",
    "RelayBillingProtocol",
    "RelayChargeBreakdown",
    "RelayPriceEstimatorProtocol",
    "RelayUsageRecord",
    "RelayUsageReservation",
    "RelayUsageScope",
    "RelayUsageStoreProtocol",
    "ResourceExhaustedError",
    "ResourceQuota",
    "ResourceUnit",
    "ResourceUsageResult",
    "ResourceUsageSnapshot",
    "ResourceWindowKind",
    "billing_store_unavailable",
    "charge_overflow",
    "duplicate_settlement",
    "invalid_usage",
    "quota_exhausted",
    "reservation_expired",
    "unknown_price",
]
