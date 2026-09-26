"""Base repository protocol.

Defines the standard repository interface for aggregate persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Generic, TypeVar

from quadkit.events.aggregates.aggregate import AggregateRoot

if TYPE_CHECKING:
    from uuid import UUID

TAggregate = TypeVar("TAggregate", bound=AggregateRoot)


class AbstractRepository(ABC, Generic[TAggregate]):
    """Abstract base repository for aggregate persistence.

    Repositories provide collection-like access to aggregates,
    abstracting away the persistence mechanism.

    Example:
        ```python
        class OrderRepository(AbstractRepository[Order]):
            async def get(self, id: UUID) -> Order | None:
                ...

            async def save(self, aggregate: Order) -> None:
                ...
        ```
    """

    @abstractmethod
    async def get(self, aggregate_id: UUID | str) -> TAggregate | None:
        """Get an aggregate by ID.

        Args:
            aggregate_id: The aggregate identifier

        Returns:
            The aggregate if found, None otherwise
        """
        ...

    @abstractmethod
    async def save(self, aggregate: TAggregate) -> None:
        """Save an aggregate.

        This persists any pending changes and clears the pending events.

        Args:
            aggregate: The aggregate to save
        """
        ...

    @abstractmethod
    async def exists(self, aggregate_id: UUID | str) -> bool:
        """Check if an aggregate exists.

        Args:
            aggregate_id: The aggregate identifier

        Returns:
            True if the aggregate exists
        """
        ...


class AbstractReadOnlyRepository(ABC, Generic[TAggregate]):
    """Read-only repository interface.

    Useful for query-side repositories in CQRS.
    """

    @abstractmethod
    async def get(self, aggregate_id: UUID | str) -> TAggregate | None:
        """Get an aggregate by ID."""
        ...

    @abstractmethod
    async def exists(self, aggregate_id: UUID | str) -> bool:
        """Check if an aggregate exists."""
        ...

    @abstractmethod
    async def get_all(
        self,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[TAggregate]:
        """Get all aggregates with pagination."""
        ...


__all__ = ["AbstractReadOnlyRepository", "AbstractRepository"]
