"""SQL Repository pattern implementation for the Quadkit DB package.

Provides :class:`SQLRepository`, a concrete SQL-backed implementation of
``AbstractRepository`` from ``quadkit.data``.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, TypeVar, cast

from quadkit.contracts.data.identifiers import Column, Table
from quadkit.logging import get_logger
from quadkit.primitives.data import AbstractRepository
from quadkit.sql.context.keys import TENANT_ID
from quadkit.sql.repositories._advanced_mixin import _AdvancedMixin
from quadkit.sql.repositories._filter_mixin import _FilterMixin
from quadkit.sql.repositories._read_mixin import _ReadMixin
from quadkit.sql.repositories._rls_mixin import _RLSMixin
from quadkit.sql.repositories._write_mixin import _WriteMixin

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol
    from quadkit.sql.context import DbContext
    from quadkit.sql.row_level_security import RowLevelSecurityPolicy

logger = get_logger(__name__)

TEntity = TypeVar("TEntity")
TKey = TypeVar("TKey")


class SQLRepository(  # type: ignore[misc]
    _RLSMixin,
    _FilterMixin,
    _ReadMixin,
    _WriteMixin,
    _AdvancedMixin,
    AbstractRepository[TEntity, TKey],
):
    """SQL-backed implementation of ``AbstractRepository``.

    All identifier arguments (``table_name``, ``key_field``) are validated
    and quoted at construction time using the :mod:`quadkit.sql.sql`
    type-safe identifier system.  Column names from callers (``columns``,
    ``sort_by``, ``field_spec``) are validated at the API boundary before
    being interpolated into SQL.
    """

    def __init__(
        self,
        provider: DatabaseProviderProtocol,
        table_name: str,
        key_field: str = "id",
        soft_delete_enabled: bool = False,
        multi_tenant: bool = False,
        db_ctx: DbContext | None = None,
        rls_policy: RowLevelSecurityPolicy | None = None,
    ) -> None:
        super().__init__()
        self.provider = provider
        self.table_name = table_name
        self.key_field = key_field
        self.soft_delete_enabled = soft_delete_enabled
        self.multi_tenant = multi_tenant
        self._db_ctx = db_ctx
        if multi_tenant and db_ctx is None:
            raise ValueError(
                "multi_tenant=True requires db_ctx; pass a DbContext from create_db_context()"
            )
        self._rls_policy = rls_policy
        self._write_table_name: str | None = None
        self._read_only_fields: list[str] = []
        self._table = Table(table_name)
        self._key_col = Column(key_field)
        # Validated + quoted table name string
        self._safe_table_name = str(self._table)
        # Resolved on demand by `table_columns()`; `None` until then.
        self._table_columns: frozenset[str] | None = None
        self._table_column_types: dict[str, str] = {}
        self._table_columns_resolved = False

    async def table_columns(self) -> frozenset[str] | None:
        """Return the table's real column names, or ``None`` if unknown.

        ``create`` and ``upsert`` stamp ``created_at`` / ``updated_at`` onto an
        entity that omits them, which is the framework's audit convention. Not
        every table follows it: a key/value settings table keeps ``updated_at``
        and no ``created_at``; a join table keeps neither. Stamping a column
        the table does not have is not a soft failure — the INSERT is rejected
        (``table settings has no column named created_at``) before any row
        lands — so the write path asks the schema instead of assuming.

        Resolved once per repository instance and cached; a table's columns do
        not change while a repository object exists. ``None`` means the
        provider could not answer (it predates ``get_table_columns``, or the
        probe failed), in which case callers keep stamping both columns —
        the behaviour every host had before this method existed.

        Returns:
            The table's column names, or ``None`` when unresolvable.
        """
        if self._table_columns_resolved:
            return self._table_columns
        self._table_columns_resolved = True

        probe = getattr(self.provider, "get_table_columns", None)
        if not callable(probe):
            return None
        try:
            rows = await probe(self.write_table_name)
        except Exception:  # noqa: BLE001 -- schema probe is best-effort; see docstring
            logger.debug("table_columns_unavailable table=%s", self.write_table_name)
            return None

        col_types: dict[str, str] = {}
        for row in rows or ():
            if isinstance(row, dict) and row.get("name"):
                col_name = str(row["name"])
                col_types[col_name] = str(row.get("type") or "").lower()
        # An empty answer is indistinguishable from "no such table"; treat it as
        # unknown rather than as a table with no columns, so a typo'd table name
        # does not silently disable timestamp stamping.
        self._table_column_types = col_types
        self._table_columns = frozenset(col_types) if col_types else None
        return self._table_columns

    @property
    def write_table_name(self) -> str:
        """Table name used for write operations (INSERT, UPDATE, DELETE)."""
        return self._write_table_name or self.table_name

    @write_table_name.setter
    def write_table_name(self, value: str) -> None:
        self._write_table_name = value

    @property
    def read_only_fields(self) -> list[str]:
        """Fields excluded from write operations."""
        return self._read_only_fields

    @read_only_fields.setter
    def read_only_fields(self, value: list[str]) -> None:
        self._read_only_fields = value

    # ------------------------------------------------------------------
    # Required abstract methods (subclasses must implement)
    # ------------------------------------------------------------------

    @abstractmethod
    def _entity_to_dict(self, entity: TEntity) -> dict[str, Any]:
        """Convert *entity* to a plain dictionary for database operations.

        Args:
            entity: The entity to serialize.

        Returns:
            Dictionary of column -> value pairs.
        """

    @abstractmethod
    def _row_to_entity(self, row: dict[str, Any]) -> TEntity:
        """Convert a database *row* dictionary to an entity instance.

        Args:
            row: Raw row dict returned by the database provider.

        Returns:
            Constructed entity instance.
        """

    # ------------------------------------------------------------------
    # AbstractRepository primitives
    # ------------------------------------------------------------------

    async def _fetch_by_id(self, entity_id: Any) -> TEntity | None:
        """Retrieve a single entity by primary key (delegates to find_by_id).

        Args:
            entity_id: Primary key value.

        Returns:
            The entity or ``None``.
        """
        return cast("TEntity | None", await self.find_by_id(entity_id))

    async def _fetch_many(
        self,
        *,
        skip: int,
        limit: int,
        filters: dict[str, Any],
    ) -> list[TEntity]:
        """Retrieve a filtered, paginated list (delegates to find_many).

        Args:
            skip: Number of rows to skip.
            limit: Maximum rows to return.
            filters: Attribute equality filters.

        Returns:
            Matching entities.
        """
        return await self.find_many(offset=skip, limit=limit, **filters)

    async def _count(self, *, filters: dict[str, Any]) -> int:
        """Count matching entities via direct SQL (avoids recursion with count()).

        Args:
            filters: Attribute equality filters.

        Returns:
            Count of matching entities.
        """
        from quadkit.sql.exceptions import (
            DatabaseConnectionError,
            DatabaseError,
            DatabaseTimeoutError,
            QueryError,
            RepositoryError,
        )

        try:
            base_query = f"SELECT COUNT(*) as count FROM {self._table}"  # noqa: S608 -- self._table is a validated, quoted Table() identifier
            params: list[Any] = []
            query = await self._apply_filters_to_query(
                base_query, params, dict(filters)
            )
            result = await self.provider.execute_query(query, params)
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
        ) as err:
            raise RepositoryError("Failed to count entities with criteria") from err
        else:
            if result.success and result.rows:
                return int(result.rows[0]["count"])
            return 0

    async def _save(self, entity: TEntity) -> TEntity:
        """Insert or update *entity* depending on whether its key is set.

        Args:
            entity: Entity to persist.

        Returns:
            The persisted entity.
        """
        key_value = (
            entity.get(self.key_field)
            if isinstance(entity, dict)
            else getattr(entity, self.key_field, None)
        )
        if key_value is None:
            return cast("TEntity", await self.create(entity))
        return cast("TEntity", await self.update(entity))

    async def _delete(self, entity_id: Any) -> bool:
        """Delete entity by primary key (delegates to delete_by_id).

        Args:
            entity_id: Primary key of entity to remove.

        Returns:
            ``True`` if deleted, ``False`` otherwise.
        """
        return await self.delete_by_id(entity_id)

    @asynccontextmanager
    async def with_tenant_scope(self, tenant_id: str) -> AsyncGenerator[None, None]:
        """Async context manager that scopes the repo to *tenant_id*.

        Sets the db-context ``TENANT_ID`` for the block and resets it on
        exit, mirroring :meth:`_RLSMixin.with_admin_scope` for the
        no-active-scope case.  These two context managers are the *only*
        ways a ``multi_tenant`` repository runs without an ambient tenant.

        Example::

            async with repo.with_tenant_scope("tenant-abc"):
                rows = await repo.find_many()   # WHERE tenant_id = 'tenant-abc'

        Args:
            tenant_id: The tenant to scope the block to.

        Yields:
            ``None`` — the body runs tenant-scoped.

        Raises:
            RuntimeError: If the repository has no ``db_ctx`` configured.
        """
        if self._db_ctx is None:
            raise RuntimeError(
                "with_tenant_scope() called on a repository that has no db_ctx configured."
            )
        token = self._db_ctx.set(TENANT_ID, tenant_id)
        try:
            yield
        finally:
            self._db_ctx.reset(TENANT_ID, token)

    # ------------------------------------------------------------------
    # High-level convenience method (entity OR primary-key value)
    # ------------------------------------------------------------------

    async def delete(self, entity_or_id: Any) -> bool:
        """Delete by entity object or primary key value.

        Args:
            entity_or_id: An entity dict/object with the primary key attribute,
                or a bare primary key value.

        Returns:
            ``True`` if the entity was deleted.

        Raises:
            RepositoryError: If the primary key cannot be resolved.
        """
        from quadkit.sql.exceptions import RepositoryError

        if isinstance(entity_or_id, dict):
            key = entity_or_id.get(self.key_field)
        else:
            key = getattr(entity_or_id, self.key_field, entity_or_id)
        if key is None:
            raise RepositoryError("Entity must have a primary key value for deletion")
        deleted = await self.delete_by_id(key)
        for hook in self._post_delete_hooks:
            await hook(key)
        return deleted
