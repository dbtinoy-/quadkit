"""SpecificationProtocol pattern relocated into domain package."""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class SpecificationProtocol(Protocol[T]):
    """Protocol for the SpecificationProtocol pattern.

    This class was previously defined in ``quadkit.contracts.specification``
    before the 2026 reorg.  It has been moved here alongside the other
    DDD primitives.  A migration mapping ensures imports are rewritten.
    """

    def is_satisfied_by(self, candidate: T) -> bool: ...

    def __and__(self, other: SpecificationProtocol[T]) -> SpecificationProtocol[T]: ...

    def __or__(self, other: SpecificationProtocol[T]) -> SpecificationProtocol[T]: ...

    def __invert__(self) -> SpecificationProtocol[T]: ...


__all__ = ["SpecificationProtocol", "T"]
