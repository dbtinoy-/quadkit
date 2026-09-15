"""Exceptions for the domain subsystem.

Provides a typed domain exception hierarchy and aggregates related
exceptions from ``quadkit-contracts``.
"""

from __future__ import annotations

from quadkit.contracts.data.exceptions import UnitOfWorkError as UnitOfWorkError
from quadkit.contracts.exceptions import QuadkitError
from quadkit.contracts.exceptions.domain import (
    DomainError as DomainError,
)
from quadkit.contracts.exceptions.domain import (
    FieldError as FieldError,
)
from quadkit.contracts.exceptions.domain import (
    ValidationError as ValidationError,
)


class DomainPolicyViolationError(QuadkitError):
    """Raised when a domain policy evaluation fails.

    Distinct from ``PolicyViolationProtocol`` (the Result-pattern error descriptor);
    this is the exception form for cases where the policy failure propagates
    as an unexpected infrastructure or wiring error.
    """

    _code = "QK_ERR_DOM_009"

    def __init__(self, policy_name: str, message: str) -> None:
        self.policy_name = policy_name
        super().__init__(
            message=message,
            details={"policy_name": policy_name},
        )


__all__ = [
    "DomainError",
    "DomainPolicyViolationError",
    "FieldError",
    "UnitOfWorkError",
    "ValidationError",
]
