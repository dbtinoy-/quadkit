"""In-memory repository for development, testing, and prototyping.

Provides a generic, async-safe in-memory implementation of the RepositoryProtocol
pattern backed by :class:`~quadkit.data.repository.base.AbstractRepository`.
Intended as a zero-infrastructure drop-in for unit tests and local development.
For production, replace with ``quadkit-sql``'s SQLRepository or a
domain-specific storage backend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from quadkit.concurrency.locks.rwlock import AsyncRWLock
from quadkit.primitives.data import AbstractRepository

if TYPE_CHECKING:
    from quadkit.contracts.domain.specification import SpecificationProtocol

T = TypeVar("T")


class InMemoryRepository(AbstractRepository[T, Any], Generic[T]):
    """Generic async in-memory repository for **testing and development only**.

    This class lives in ``quadkit-testing`` intentionally — it is not exported
    from ``quadkit`` core.  Production code should depend on the
    ``RepositoryProtocol`` protocol from ``quadkit.contracts.data`` and receive a
    concrete implementation (e.g. ``SQLRepository`` from ``quadkit-sql``)
    via dependency injection.

    Stores entities in a plain dict keyed by their identity attribute.
    Write operations acquire an exclusive write lock via ``AsyncRWLock``;
    read operations acquire a shared read lock, allowing concurrent reads
    while serialising writes. Safe for single-event-loop async usage.

    Extends :class:`~quadkit.data.repository.base.AbstractRepository` and
    implements all required primitives.  For production persistence, use
    ``quadkit-sql``'s ``SQLRepository`` or any other storage backend.

    Args:
        id_attr: Name of the entity attribute that holds the primary key.
            Defaults to ``"id"``.

    Example::

        repo = InMemoryRepository[User]()
        user = await repo.save(User(id="u1", name="Alice"))
        found = await repo.get("u1")
    """

    def __init__(self, id_attr: str = "id") -> None:
        super().__init__()
        self._store: dict[Any, T] = {}
        self._id_attr = id_attr
        self._lock = AsyncRWLock()

    # ------------------------------------------------------------------
    # AbstractRepository primitives
    # ------------------------------------------------------------------

    async def _fetch_by_id(self, entity_id: Any) -> T | None:
        async with self._lock.read():
            return self._store.get(entity_id)

    async def _fetch_many(
        self,
        *,
        skip: int,
        limit: int,
        filters: dict[str, Any],
    ) -> list[T]:
        async with self._lock.read():
            if filters:
                items = [
                    item
                    for item in self._store.values()
                    if all(getattr(item, k, None) == v for k, v in filters.items())
                ]
            else:
                items = list(self._store.values())
            return items[skip : skip + limit]

    async def _count(self, *, filters: dict[str, Any]) -> int:
        async with self._lock.read():
            if filters:
                return sum(
                    1
                    for item in self._store.values()
                    if all(getattr(item, k, None) == v for k, v in filters.items())
                )
            return len(self._store)

    async def find_by_spec(self, spec: SpecificationProtocol[T]) -> list[T]:
        """Return all entities satisfying the given specification.

        Args:
            spec: A ``SpecificationProtocol`` object implementing ``is_satisfied_by``.

        Returns:
            List of entities for which ``spec.is_satisfied_by(entity)`` is True.
        """
        async with self._lock.read():
            return [item for item in self._store.values() if spec.is_satisfied_by(item)]

    async def _save(self, entity: T) -> T:
        async with self._lock.write():
            entity_id = getattr(entity, self._id_attr)
            self._store[entity_id] = entity
            return entity

    async def _delete(self, entity_id: Any) -> bool:
        async with self._lock.write():
            return self._store.pop(entity_id, None) is not None

    # ------------------------------------------------------------------
    # Extra convenience methods (beyond the RepositoryProtocol protocol)
    # ------------------------------------------------------------------

    async def find_by(self, **criteria: Any) -> list[T]:
        """Return all entities whose attributes match all given criteria.

        Args:
            **criteria: Keyword arguments mapping attribute names to
                expected values.

        Returns:
            List of matching entities.
        """
        async with self._lock.read():
            return [
                item
                for item in self._store.values()
                if all(getattr(item, k, None) == v for k, v in criteria.items())
            ]

    async def find_one_by(self, **criteria: Any) -> T | None:
        """Return the first entity matching the given criteria, or ``None``.

        Args:
            **criteria: Keyword arguments mapping attribute names to
                expected values.

        Returns:
            The first matching entity, or ``None``.
        """
        results = await self.find_by(**criteria)
        return results[0] if results else None

    async def find_by_filter(
        self, filter_model: Any, *, skip: int = 0, limit: int = 100
    ) -> list[T]:
        """Mock find_by_filter."""
        return []

    async def find_by_query(self, query: Any) -> list[T]:
        """Mock find_by_query."""
        return []

    async def exists(self, entity_id: Any) -> bool:
        """Check whether an entity with the given ID exists.

        Args:
            entity_id: Primary key value to check.

        Returns:
            ``True`` if the entity exists, ``False`` otherwise.
        """
        async with self._lock.read():
            return entity_id in self._store

    async def save_many(self, entities: list[T]) -> list[T]:
        """Persist multiple entities atomically within a single lock acquisition.

        Args:
            entities: List of entities to store.

        Returns:
            The same list of entities, unmodified.
        """
        async with self._lock.write():
            for entity in entities:
                entity_id = getattr(entity, self._id_attr)
                self._store[entity_id] = entity
            return entities

    async def delete_many(self, entity_ids: list[Any]) -> int:
        """Remove multiple entities by their IDs.

        Args:
            entity_ids: List of primary keys to delete.

        Returns:
            Count of entities that were actually removed.
        """
        async with self._lock.write():
            count = 0
            for eid in entity_ids:
                if self._store.pop(eid, None) is not None:
                    count += 1
            return count


__all__ = ["InMemoryRepository"]
