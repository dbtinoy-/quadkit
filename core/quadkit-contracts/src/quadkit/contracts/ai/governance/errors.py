"""Governance error classes."""

from __future__ import annotations

from quadkit.contracts.exceptions import QuadkitError


class GovernanceError(QuadkitError):
    """Base class for governance-related errors."""

    _code = "QK_ERR_GOV_001"


class BudgetExceededError(GovernanceError):
    """Error raised when budget is exceeded."""

    _code = "QK_ERR_GOV_002"


class PolicyViolationError(GovernanceError):
    """Error raised when policy is violated."""

    _code = "QK_ERR_GOV_003"


__all__ = [
    "BudgetExceededError",
    "GovernanceError",
    "PolicyViolationError",
]
