"""Governance value types and enums.

The data classes and enums the governance protocols exchange. They live here,
not in the package namespace, so `from quadkit.contracts.ai.governance.models
import GovernanceDecision` imports the type without executing the package
`__init__` — the export rule documented in `AGENTS.md` §4.5.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

__all__ = ["AIAuditEvent", "AuditEventType", "GovernanceDecision"]


@dataclass(frozen=True)
class GovernanceDecision:
    """Decision from the governance layer."""

    allowed: bool
    reason: str | None = None
    remaining_budget: float | None = None


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
