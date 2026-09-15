"""Type definitions for the mapping subsystem.

TypeVars and aliases for source/destination types and mapper callables.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol, TypeAlias, TypeVar

S = TypeVar("S")  # Source object type
D = TypeVar("D")  # Destination object type
S_contra = TypeVar(
    "S_contra", contravariant=True
)  # Source type (contravariant — consumed as input)

MappingFn: TypeAlias = Callable[[S], D]  # Simple single-argument mapper callable


class MapperProtocol(Protocol[S_contra, D]):
    """Protocol for type-safe object-to-object mappers."""

    def map(self, source: S_contra, dest_type: type[D]) -> D:
        """Map a single *source* instance to *dest_type*."""
        ...

    def map_many(self, sources: Iterable[S_contra], dest_type: type[D]) -> list[D]:
        """Map an iterable of *sources* to a list of *dest_type* instances."""
        ...


__all__ = [
    "D",
    "MapperProtocol",
    "MappingFn",
    "S",
    "S_contra",
]
