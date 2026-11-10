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

    async def create(self, entity: Any) -> TEntity:
        """Create *entity* and return a typed ``TEntity`` when ``entity_class`` is configured."""
        if self.entity_class is not dict and isinstance(entity, dict):
            import dataclasses

            try:
                typed_entity = self._row_to_entity(dict(entity))
                typed_dict = self._entity_to_dict(typed_entity)
            except Exception:  # noqa: BLE001 — fall back when DB column defaults supply omitted required fields
                pass
            else:
                declared_fields = (
                    {f.name for f in dataclasses.fields(typed_entity)}
                    if dataclasses.is_dataclass(typed_entity)
                    else set(typed_dict.keys())
                )
                if set(entity.keys()) <= declared_fields:
                    return cast("TEntity", await super().create(typed_entity))
                columns = await self.table_columns()
                if columns:
                    entity = {
                        **{k: v for k, v in typed_dict.items() if k in columns},
                        **{k: v for k, v in entity.items() if k in columns},
                    }

        created = await super().create(entity)
        if self.entity_class is dict or not isinstance(created, dict):
            return cast("TEntity", created)
        try:
            return self._row_to_entity(created)
        except Exception:  # noqa: BLE001 — fall back to re-fetching full row if DB defaults were omitted
            key_val = created.get(self.key_field)
            if key_val is not None:
                found = await self.find_by_id(key_val)
                if found is not None:
                    return cast("TEntity", found)
            raise

    async def update(
        self,
        entity: Any,
        check_version: bool | None = None,
    ) -> TEntity:
        """Update *entity* and return a typed ``TEntity`` when ``entity_class`` is configured."""
        updated = await super().update(entity, check_version=check_version)
        if self.entity_class is dict or not isinstance(updated, dict):
            return cast("TEntity", updated)
        try:
            return self._row_to_entity(updated)
        except Exception:  # noqa: BLE001 — partial dict update lacks non-updated required fields
            key_val = updated.get(self.key_field)
            if key_val is not None:
                found = await self.find_by_id(key_val)
                if found is not None:
                    return cast("TEntity", found)
            return cast("TEntity", updated)

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
