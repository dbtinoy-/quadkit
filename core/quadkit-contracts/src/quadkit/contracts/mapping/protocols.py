"""Object mapping protocols for the Quadkit Framework.

Defines the contract for registry-based object-to-object transformation,
enabling decoupled mapping between domain models, DTOs, and other types.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

S = TypeVar("S")
D = TypeVar("D")


@runtime_checkable
class ObjectMapperProtocol(Protocol):
    """Protocol for a registry-based object-to-object mapper.

    Provides a clean map() API for converting between registered type pairs
    without ad-hoc conversion logic scattered through the codebase.
    """

    def map(
        self,
        source: Any,
        dest_type: type[Any],
        *,
        validate: bool = False,
        validator: Any | None = None,
    ) -> Any:
        """Map a source object to the destination type.

        Uses a registered mapping function to transform the source instance
        into an instance of dest_type.

        Args:
            source: The source object to transform.
            dest_type: The target type to produce.
            validate: Whether to validate the result after mapping.
            validator: Optional validator instance to use.

        Returns:
            A new instance of dest_type.

        Raises:
            MappingNotFoundError: If no mapping is registered for this type pair.
        """
        ...

    def register(
        self,
        source_type: type[Any],
        dest_type: type[Any],
        mapper_func: Any,
    ) -> None:
        """Register a mapping function from source_type to dest_type.

        Args:
            source_type: The type to map from.
            dest_type: The type to map to.
            mapper_func: A callable that accepts a source instance and returns
                a dest instance.
        """
        ...


__all__ = ["ObjectMapperProtocol"]
