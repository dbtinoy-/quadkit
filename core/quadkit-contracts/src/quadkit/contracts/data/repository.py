"""RepositoryProtocol protocols.

Generic repository patterns for data access abstraction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.domain.specification import SpecificationProtocol

T = TypeVar("T")


@runtime_checkable
class ReadOnlyRepositoryProtocol(Protocol, Generic[T]):
    """Protocol for read-only repository operations.

    Use this for query-only access patterns (CQRS query side).

    Example:
        ```python
        class UserQueryRepository:
            async def get(self, id: str) -> User | None:
                return await self.db.query("users").where(id=id).first()

            async def list(self, skip: int = 0, limit: int = 100) -> list[User]:
                return await self.db.query("users").offset(skip).limit(limit).all()
        ```
    """

    async def get(self, item_id: str) -> T | None:
        """Get entity by ID.

        Args:
            item_id: Entity identifier.

        Returns:
            Entity if found, None otherwise.
        """
        ...

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[T]:
        """List entities with pagination.

        Args:
            skip: Number of records to skip.
            limit: Maximum records to return.
            **filters: Optional filter criteria.

        Returns:
            List of entities.
        """
        ...

    async def find_by_spec(self, spec: SpecificationProtocol[T]) -> list[T]:  # type: ignore[valid-type]
        """Find entities matching a complex specification.

        Args:
            spec: The DDD specification to evaluate.

        Returns:
            List of matching entities.
        """
        ...

    async def count(self, **filters: Any) -> int:
        """Count entities matching filters.

        Args:
            **filters: Optional filter criteria.

        Returns:
            Total count of matching entities.
        """
        ...


@runtime_checkable
class RepositoryProtocol(ReadOnlyRepositoryProtocol[T], Protocol, Generic[T]):
    """Protocol for full repository operations.

    Extends ReadOnlyRepositoryProtocol with write operations.

    Example:
        ```python
        class UserRepository:
            async def save(self, entity: User) -> User:
                if entity.id:
                    await self.db.update("users", entity.dict()).where(id=entity.id)
                else:
                    entity.id = await self.db.insert("users", entity.dict())
                return entity

            async def delete(self, id: str) -> bool:
                result = await self.db.delete("users").where(id=id)
                return result.affected_rows > 0
        ```
    """

    async def save(self, entity: T) -> T:
        """Save (create or update) an entity.

        Args:
            entity: Entity to save.

        Returns:
            Saved entity with any generated fields populated.
        """
        ...

    async def delete(self, item_id: str) -> bool:
        """Delete entity by ID.

        Args:
            item_id: Entity identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def save_many(self, entities: list[T]) -> list[T]:
        """Save (create or update) multiple entities in a single operation.

        Implementations SHOULD execute this as a batch for efficiency.

        Args:
            entities: Entities to save.

        Returns:
            Saved entities with any generated fields populated.
        """
        ...

    async def delete_many(self, item_ids: list[str]) -> int:
        """Delete multiple entities by ID.

        Implementations SHOULD execute this as a batch for efficiency.

        Args:
            item_ids: Entity identifiers to delete.

        Returns:
            Number of entities actually deleted.
        """
        ...


__all__ = [
    "ReadOnlyRepositoryProtocol",
    "RepositoryProtocol",
    "T",
]
