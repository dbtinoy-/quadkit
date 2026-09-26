"""Simple Generic RepositoryProtocol implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, cast

from quadkit.contracts import DatabaseProviderProtocol
from quadkit.di.decorators import inject
from quadkit.sql.exceptions import RepositoryError
from quadkit.sql.repositories.base import SQLRepository
from quadkit.sql.repositories.filter_objects import Filter

if TYPE_CHECKING:
    from quadkit.sql.row_level_security import RowLevelSecurityPolicy

TEntity = TypeVar("TEntity")
TKey = TypeVar("TKey")


@inject
class GenericRepository(SQLRepository[TEntity, TKey], Generic[TEntity, TKey]):
    """
    Generic repository with type safety.

    Provides strongly-typed CRUD operations for entities.
    """

    def __init__(
        self,
        provider: DatabaseProviderProtocol,
        table_name: str,
        entity_class: type[TEntity],
        key_field: str = "id",
        soft_delete_enabled: bool = False,
        multi_tenant: bool | None = None,
        rls_policy: RowLevelSecurityPolicy | None = None,
    ):
        if multi_tenant is None:
            multi_tenant = getattr(entity_class, "is_multi_tenant", False)

        super().__init__(
            provider,
            table_name,
            key_field,
            soft_delete_enabled,
            multi_tenant=multi_tenant,
            rls_policy=rls_policy,
        )
        self.entity_class = entity_class

    def _entity_to_dict(self, entity: TEntity) -> dict[str, Any]:
        """Convert entity to dictionary."""
        from quadkit.domain import DomainModel

        if isinstance(entity, DomainModel):
            # DomainModel (dataclass-based)
            return entity.model_dump()
        if hasattr(entity, "__dict__"):
            return entity.__dict__.copy()
        if isinstance(entity, dict):
            return entity.copy()
        raise RepositoryError(
            f"Cannot convert entity of type {type(entity)} to dict",
        )

    def _row_to_entity(self, row: dict[str, Any]) -> TEntity:
        """Convert database row to entity."""
        from quadkit.domain import DomainModel

        if self.entity_class is dict:
            return cast("TEntity", row)

        # Entity mapping and validation
        if issubclass(self.entity_class, DomainModel):
            # DomainModel (dataclass-based)
            return cast("TEntity", self.entity_class.model_validate(row))
        # Regular class constructor
        return self.entity_class(**row)

    # ------------------------------------------------------------------
    # Convenience aliases
    # ------------------------------------------------------------------

    async def find(
        self,
        filters: dict[str, Any]
        | Filter
        | list[Filter]
        | tuple[Filter, ...]
        | None = None,
        limit: int | None = None,
        offset: int | None = 0,
        sort_by: str | None = None,
        sort_order: str = "asc",
        columns: list[str] | None = None,
        include_deleted: bool = False,
    ) -> list[TEntity]:
        """Find entities with optional dict-style filters.

        Convenience wrapper around ``find_many()`` that accepts ``filters``
        as a plain dict instead of ``**kwargs``.
        """
        typed_filters: tuple[Filter, ...] = ()
        keyword_filters: dict[str, Any] = {}

        if isinstance(filters, Filter):
            typed_filters = (filters,)
        elif isinstance(filters, (list, tuple)):
            typed_filters = tuple(filters)
        elif filters is not None:
            keyword_filters = filters

        return await self.find_many(
            *typed_filters,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            columns=columns,
            include_deleted=include_deleted,
            **keyword_filters,
        )

    async def count(
        self,
        filters: dict[str, Any]
        | Filter
        | list[Filter]
        | tuple[Filter, ...]
        | None = None,
        *filter_expressions: Any,
        include_deleted: bool = False,
        **kwargs: Any,
    ) -> int:
        """Count entities with optional dict-style filters.

        Convenience wrapper around the mixin ``count()`` that accepts
        ``filters`` as a plain dict (or ``Filter`` objects) instead of
        ``**kwargs``, mirroring :meth:`find`.
        """
        typed_filters: tuple[Filter, ...] = ()
        keyword_filters: dict[str, Any] = {}

        if isinstance(filters, Filter):
            typed_filters = (filters,)
        elif isinstance(filters, (list, tuple)):
            typed_filters = tuple(filters)
        elif filters is not None:
            keyword_filters = filters

        keyword_filters.update(kwargs)
        return await super().count(
            *typed_filters,
            *filter_expressions,
            include_deleted=include_deleted,
            **keyword_filters,
        )

    async def get(self, key: TKey) -> TEntity | None:  # type: ignore[override]
        """Get a single entity by primary key.

        Convenience alias for ``find_by_id()``.
        """
        return cast("TEntity | None", await self.find_by_id(key))

    async def save_many(self, entities: list[TEntity]) -> list[TEntity]:
        """Persist *entities*, creating or updating each as appropriate.

        ``RepositoryProtocol`` declares the batch primitives as ``...`` stubs,
        so an implementation that does not override them answers ``None`` to
        every caller. This delegates to :meth:`save` in input order, which
        keeps the returned list aligned with *entities* and runs the
        post-save hooks once per entity.

        Args:
            entities: Entities to save.

        Returns:
            The saved entities, in input order.
        """
        return [await self.save(entity) for entity in entities]

    async def delete_many(self, item_ids: list[TKey]) -> int:  # type: ignore[override]
        """Delete every entity whose primary key appears in *item_ids*.

        Delegates to :meth:`delete` so the post-delete hooks run for each
        entity actually removed.

        Args:
            item_ids: Primary keys of the entities to delete.

        Returns:
            Number of entities actually deleted.
        """
        outcomes = [await self.delete(item_id) for item_id in item_ids]
        return sum(1 for deleted in outcomes if deleted)
