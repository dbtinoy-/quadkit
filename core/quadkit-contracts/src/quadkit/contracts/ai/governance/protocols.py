"""Protocols for AI governance, cost tracking and audit persistence.

Concrete definitions of the governance contracts; the package `__init__`
re-exports them.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from quadkit.contracts.ai.governance.models import AIAuditEvent, GovernanceDecision

__all__ = [
    "AIAuditStoreProtocol",
    "AIGovernanceProtocol",
    "CostTrackingProtocol",
]


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
