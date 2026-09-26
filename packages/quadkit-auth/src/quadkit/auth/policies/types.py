"""Core types for Quadkit ABAC Policy Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class PolicyEffect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class DecisionOutcome(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    INDETERMINATE = "indeterminate"


@dataclass(frozen=True)
class Condition:
    """A condition that must be met for a policy to apply."""

    attribute: str
    operator: str
    value: Any


@dataclass(frozen=True)
class Policy:
    """A granular authorization policy."""

    policy_id: str
    name: str
    effect: PolicyEffect
    principals: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    priority: int = 0
    description: str | None = None


@dataclass(frozen=True)
class AuthorizationRequest:
    """A request for authorization evaluation."""

    principal: str  # e.g., "user:123"
    action: str  # e.g., "read"
    resource: str  # e.g., "document:456"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorizationDecision:
    """The result of an authorization evaluation."""

    decision: DecisionOutcome
    reason: str | None = None
    applied_policies: list[str] = field(default_factory=list)


__all__ = [
    "AuthorizationDecision",
    "AuthorizationRequest",
    "Condition",
    "DecisionOutcome",
    "Policy",
    "PolicyEffect",
]
