"""Read-only mapper protocol for data transformation contracts.

Defines the contract for mapping between domain/storage models without
mutating either side.
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar, runtime_checkable

S = TypeVar("S")
T = TypeVar("T")

__all__ = ["DataMapperProtocol", "ReadOnlyMapperProtocol", "S", "T"]


@runtime_checkable
class ReadOnlyMapperProtocol(Protocol, Generic[S, T]):
    """Protocol for a stateless, read-only mapper between two types.

    Implementations translate a source model of type ``S`` to a target
    model of type ``T`` without modifying either. The batch variant
    is provided for efficiency when mapping large collections.
    """

    def to_target(self, source: S) -> T:
        """Map a single source instance to the target type.

        Args:
            source: Source model instance to translate.

        Returns:
            Corresponding target model instance.
        """
        ...

    def to_target_batch(self, sources: list[S]) -> list[T]:
        """Map a sequence of source instances to the target type.

        Args:
            sources: Sequence of source model instances to translate.

        Returns:
            List of corresponding target model instances in the same order.
        """
        ...


@runtime_checkable
class DataMapperProtocol(ReadOnlyMapperProtocol[S, T], Protocol, Generic[S, T]):
    """Protocol for a bidirectional stateless mapper between two types.

    Extends :class:`ReadOnlyMapperProtocol` with the ability to map from
    the target type back to the source type, enabling round-trip
    transformations (e.g. domain model ↔ storage row).
    """

    def to_source(self, target: T) -> S:
        """Map a single target instance back to the source type.

        Args:
            target: Target model instance to translate.

        Returns:
            Corresponding source model instance.
        """
        ...

    def to_source_batch(self, targets: list[T]) -> list[S]:
        """Map a sequence of target instances back to the source type.

        Args:
            targets: Sequence of target model instances to translate.

        Returns:
            List of corresponding source model instances in the same order.
        """
        ...
