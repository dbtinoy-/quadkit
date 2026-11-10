"""Approval workflow models — step, policy, and status types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["ApprovalPolicy", "ApprovalStatus", "ApprovalStep"]


class ApprovalStatus(StrEnum):
    """Lifecycle status of an approval request or step.

    Transitions:
        PENDING → APPROVED
        PENDING → REJECTED
        PENDING → SKIPPED   (when the step's condition evaluates to False)
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class ApprovalPolicy(StrEnum):
    """Policy that governs when an :class:`ApprovalChain` is considered approved.

    Attributes:
        ALL: Every step in the chain must be approved (default).
        ANY: At least one step must be approved.
        MAJORITY: More than half of the non-skipped steps must be approved.
    """

    ALL = "all"
    ANY = "any"
    MAJORITY = "majority"


@dataclass
class ApprovalStep:
    """A single node in an :class:`ApprovalChain`.

    Attributes:
        name: Unique step identifier within the chain.
        approver: Sync or async callable that performs the approval check.
            Must return ``True`` (approved) or ``False`` (rejected).  A
            callable that raises counts as rejected (fail-closed).
        condition: Optional sync or async callable evaluated before
            *approver*.  When it returns ``False`` the step is skipped;
            when it raises the step still runs (fail-closed).  When
            ``None`` the step always runs.
        metadata: Arbitrary key-value pairs propagated to notifications
            and audit logs.
    """

    name: str
    approver: Callable[..., Awaitable[bool]]
    condition: Callable[..., Awaitable[bool]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
