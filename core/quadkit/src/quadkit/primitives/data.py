"""Abstract repository and mapper base classes for the Quadkit core layer.

Provides:
- ``AbstractReadOnlyRepository`` / ``AbstractRepository`` — concrete abstract
  bases implementing the ``ReadOnlyRepositoryProtocol`` / ``RepositoryProtocol`` protocols
  from ``quadkit.contracts.data``.
- ``ReadOnlyMapper`` / ``DataMapper`` — abstract bases for one-way and
  bidirectional type translations.

Extension packages subclass these to avoid duplicating the delegation
boilerplate without taking a cross-extension dependency.

Typical usage::

    from quadkit.primitives.data import AbstractRepository, DataMapper

    class UserRepository(AbstractRepository[User, str]):
        async def _fetch_by_id(self, entity_id: str) -> User | None: ...
        async def _fetch_many(self, *, skip, limit, filters) -> list[User]: ...
        async def _count(self, *, filters) -> int: ...
        async def find_by_spec(self, spec) -> list[User]: ...
        async def _save(self, entity: User) -> User: ...
        async def _delete(self, entity_id: str) -> bool: ...
"""

from __future__ import annotations

import abc
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from quadkit.contracts.data.repository import (
    ReadOnlyRepositoryProtocol,
    RepositoryProtocol,
)

if TYPE_CHECKING:
    from quadkit.contracts.domain.specification import SpecificationProtocol

T = TypeVar("T")
ID = TypeVar("ID")
S = TypeVar("S")

# Module-level alias so that abstract-method return annotations inside the
# class body aren't accidentally resolved to ``AbstractReadOnlyRepository.list``
# (a method with the same name as the builtin) by mypy.
_L = list


# ---------------------------------------------------------------------------
# RepositoryProtocol abstractions
# ---------------------------------------------------------------------------


class AbstractReadOnlyRepository(ReadOnlyRepositoryProtocol[T], Generic[T, ID]):
    """Abstract base for read-only repository implementations.

    Subclasses must implement the primitive read operations listed below.
    The public ``ReadOnlyRepositoryProtocol`` protocol methods are implemented here
    and delegate to those primitives.

    Abstract primitives:
        - :meth:`_fetch_by_id`
        - :meth:`_fetch_many`
        - :meth:`_count`
        - :meth:`find_by_spec`
    """

    async def get(self, item_id: Any) -> T | None:
        """Return the entity with the given ID, or ``None``.

        Args:
            item_id: Primary key value to look up.

        Returns:
            Matching entity or ``None``.
        """
        return await self._fetch_by_id(item_id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[T]:
        """Return a paginated, optionally filtered list of entities.

        Args:
            skip: Number of entities to skip.
            limit: Maximum number of entities to return.
            **filters: Optional attribute equality filters.

        Returns:
            Matching entities.
        """
        return await self._fetch_many(skip=skip, limit=limit, filters=filters)

    async def count(self, **filters: Any) -> int:
        """Return the total count of matching entities.

        Args:
            **filters: Optional attribute equality filters.

        Returns:
            Count of matching entities.
        """
        return await self._count(filters=filters)

    @abc.abstractmethod
    async def _fetch_by_id(self, entity_id: Any) -> T | None:
        """Retrieve a single entity by its primary key.

        Args:
            entity_id: Primary key value.

        Returns:
            The entity, or ``None`` if not found.
        """

    @abc.abstractmethod
    async def _fetch_many(
        self,
        *,
        skip: int,
        limit: int,
        filters: dict[str, Any],
    ) -> _L[T]:
        """Retrieve a filtered, paginated list of entities.

        Args:
            skip: Number of entities to skip.
            limit: Maximum number of entities to return.
            filters: Attribute equality filters (field → value mapping).

        Returns:
            Matching entities.
        """

    @abc.abstractmethod
    async def _count(self, *, filters: dict[str, Any]) -> int:
        """Count entities matching the given filters.

        Args:
            filters: Attribute equality filters (field → value mapping).

        Returns:
            Count of matching entities.
        """

    @abc.abstractmethod
    async def find_by_spec(
        self,
        spec: SpecificationProtocol[T],
    ) -> _L[T]:
        """Return all entities that satisfy *spec*.

        Args:
            spec: A ``SpecificationProtocol`` implementing ``is_satisfied_by``.

        Returns:
            Matching entities.
        """


class AbstractRepository(
    AbstractReadOnlyRepository[T, ID], RepositoryProtocol[T], Generic[T, ID]
):
    """Abstract base for full repository implementations.

    Extends :class:`AbstractReadOnlyRepository` with write primitives and
    optional post-save / post-delete lifecycle hooks.

    Abstract primitives:
        - All primitives from :class:`AbstractReadOnlyRepository`
        - :meth:`_save`
        - :meth:`_delete`
    """

    def __init__(self) -> None:
        self._post_save_hooks: list[Any] = []
        self._post_delete_hooks: list[Any] = []

    def register_post_save_hook(self, callback: Any) -> None:
        """Register an async callback invoked after every successful save.

        Args:
            callback: Async callable accepting the saved entity as its sole
                positional argument.
        """
        self._post_save_hooks.append(callback)

    def register_post_delete_hook(self, callback: Any) -> None:
        """Register an async callback invoked after every successful delete.

        Args:
            callback: Async callable accepting the deleted entity ID as its
                sole positional argument.
        """
        self._post_delete_hooks.append(callback)

    async def save(self, entity: T) -> T:
        """Persist *entity*, creating or updating as appropriate.

        Args:
            entity: Entity to save.

        Returns:
            The saved entity (with any generated/updated fields).
        """
        saved = await self._save(entity)
        for hook in self._post_save_hooks:
            await hook(saved)
        return saved

    async def delete(self, item_id: Any) -> bool:
        """Delete the entity with the given ID.

        Args:
            item_id: Primary key of the entity to delete.

        Returns:
            ``True`` if deleted, ``False`` if the entity did not exist.
        """
        deleted = await self._delete(item_id)
        if deleted:
            for hook in self._post_delete_hooks:
                await hook(item_id)
        return deleted

    @abc.abstractmethod
    async def _save(self, entity: T) -> T:
        """Persist (insert or update) *entity* in the backing store.

        Args:
            entity: The entity to persist.

        Returns:
            The persisted entity, with any generated fields populated.
        """

    @abc.abstractmethod
    async def _delete(self, entity_id: Any) -> bool:
        """Remove the entity with *entity_id* from the backing store.

        Args:
            entity_id: Primary key of the entity to remove.

        Returns:
            ``True`` if the entity was removed, ``False`` if it did not exist.
        """


# ---------------------------------------------------------------------------
# Mapper abstractions
# ---------------------------------------------------------------------------


class ReadOnlyMapper(Generic[S, T]):
    """Map a source value to its target representation.

    Useful for one-way projections such as entity → search document or
    entity → analytics event, where reconstruction from the target is not
    required.
    """

    @abstractmethod
    async def to_target(self, source: S) -> T:
        """Translate *source* into its target representation.

        Args:
            source: The value to translate.

        Returns:
            The target representation of *source*.
        """

    async def to_target_batch(self, sources: list[S]) -> list[T]:
        """Translate a list of sources; default implementation maps sequentially.

        Override for bulk-optimised implementations (e.g. batch ES indexing).

        Args:
            sources: Values to translate.

        Returns:
            List of target representations in the same order as *sources*.
        """
        return [await self.to_target(s) for s in sources]


class DataMapper(ReadOnlyMapper[S, T], Generic[S, T]):
    """Bidirectional mapper between a source type and a target representation.

    Extends :class:`ReadOnlyMapper` with ``to_source`` for cases where the
    target representation must be reconstructed into the domain type (e.g.
    reading a database row back into an aggregate, or deserialising a cached
    document).
    """

    @abstractmethod
    async def to_source(self, target: T) -> S:
        """Reconstruct a source value from its target representation.

        Args:
            target: The target representation to reconstruct.

        Returns:
            The reconstructed source value.
        """

    async def to_source_batch(self, targets: list[T]) -> list[S]:
        """Reconstruct a list of source values; default maps sequentially.

        Override for bulk-optimised implementations.

        Args:
            targets: Target representations to reconstruct.

        Returns:
            List of source values in the same order as *targets*.
        """
        return [await self.to_source(t) for t in targets]


__all__ = [
    "AbstractReadOnlyRepository",
    "AbstractRepository",
    "DataMapper",
    "ReadOnlyMapper",
]
