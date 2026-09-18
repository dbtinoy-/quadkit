"""Domain service and policy contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class DomainServiceProtocol(Protocol):
    """Protocol for domain services.

    Domain services encapsulate business operations that don't naturally
    belong to a single entity or value object. They should be stateless.
    """


class PolicyViolationProtocol(Protocol):
    """Describes why a policy was violated."""

    code: str
    message: str
    details: dict[str, Any]


@runtime_checkable
class PolicyProtocol(Protocol, Generic[T]):
    """Protocol for domain policies.

    A policy evaluates a domain object or operation and returns
    a Result indicating whether the policy is satisfied.
    """

    async def evaluate(self, subject: T) -> Result[T, PolicyViolationProtocol]:
        """Evaluate the policy against the subject."""
        ...


__all__ = [
    "DomainServiceProtocol",
    "PolicyProtocol",
    "PolicyViolationProtocol",
    "T",
    "T_co",
]
