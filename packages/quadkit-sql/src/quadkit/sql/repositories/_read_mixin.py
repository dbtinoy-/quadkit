"""Read mixin for SQLRepository: find_by_id, find_many, find_one, count, exists."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from quadkit.contracts.data.identifiers import Column, Table
from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
    RepositoryError,
)

logger = get_logger(__name__)


class _ReadMixin:
    """Provides ``find_by_id``, ``find_many``, ``find_one``, ``count``, ``exists``."""

    _table: Table
    _key_col: Column

    async def find_by_id(
        self,
        key: Any,
        columns: list[str] | None = None,
        include_deleted: bool = False,
    ) -> Any:
        """Retrieve a single entity by primary key.

        Args:
            key: Primary key value.
            columns: Optional list of columns to select.
            include_deleted: Whether to include soft-deleted rows.

        Returns:
            The entity or ``None``.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            fields = ", ".join(str(Column(c)) for c in columns) if columns else "*"
            query = f"SELECT {fields} FROM {self._table} WHERE {self._key_col} = ?"  # noqa: S608 -- self._table/_key_col are validated Table()/Column() identifiers
            if self.soft_delete_enabled and not include_deleted:  # type: ignore[attr-defined]
                query += " AND deleted_at IS NULL"

            param_key = str(key) if isinstance(key, UUID) else key
            rls_params: list[Any] = [param_key]
            query, rls_params = self._rls_apply(query, rls_params, "SELECT")  # type: ignore[attr-defined]
            result = await self.provider.execute_query(query, rls_params)  # type: ignore[attr-defined]
        except RepositoryError:
            raise
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
        ) as err:
            logger.exception(
                "Failed to find_by_id table=%s key=%s",
                self.table_name,  # type: ignore[attr-defined]
                key,
            )
            raise RepositoryError(f"Failed to find entity by id {key}") from err
        else:
            if result.success and result.rows:
                return self._row_to_entity(result.rows[0])  # type: ignore[attr-defined]
            return None

    async def find_many(
        self,
        *filter_expressions: Any,
        limit: int | None = None,
        offset: int | None = 0,
        sort_by: str | None = None,
        sort_order: str = "asc",
        allowed_sort_fields: list[str] | None = None,
        columns: list[str] | None = None,
        include_deleted: bool = False,
        **filters: Any,
    ) -> list[Any]:
        """Retrieve multiple entities with filtering, sorting, and pagination.

        Args:
            limit: Maximum number of rows to return.
            offset: Number of rows to skip.
            sort_by: Column name to sort by.
            sort_order: ``"asc"`` or ``"desc"``.
            allowed_sort_fields: Whitelist of sortable columns; raises if violated.
            columns: Optional column list to select.
            include_deleted: Include soft-deleted rows.
            **filters: Attribute equality (or operator) filters.

        Returns:
            List of matching entities.

        Raises:
            RepositoryError: On invalid sort field or database failure.
        """
        fields = ", ".join(str(Column(c)) for c in columns) if columns else "*"
        base_query = f"SELECT {fields} FROM {self._table}"  # noqa: S608 -- self._table is a validated Table(); fields are Column()-validated  # type: ignore[attr-defined]
        params: list[Any] = []

        initial_filters = dict(filters)

        query = await self._apply_filters_to_query(  # type: ignore[attr-defined]
            base_query,
            params,
            filters,
            include_deleted,
            filter_expressions,
        )

        if not initial_filters and " WHERE " not in query.upper():
            query += " WHERE 1=1"

        query, params = self._rls_apply(query, params, "SELECT")  # type: ignore[attr-defined]

        if sort_by:
            if allowed_sort_fields and sort_by not in allowed_sort_fields:
                raise RepositoryError(
                    f"Sorting by '{sort_by}' is not allowed. Allowed fields: {allowed_sort_fields}",
                )
            sort_col = Column(sort_by)
            direction = "DESC" if sort_order.lower() == "desc" else "ASC"
            query += f" ORDER BY {sort_col} {direction}"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        if offset and offset > 0:
            query += " OFFSET ?"
            params.append(offset)

        try:
            logger.info(
                "Executing find_many on %s: %s %s",
                getattr(self.provider, "name", "unknown"),  # type: ignore[attr-defined]
                query,
                params,
            )
            result = await self.provider.execute_query(  # type: ignore[attr-defined]
                query,
                params if params else None,
            )
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
        ) as err:
            logger.exception(
                "Failed find_many table=%s filters=%s query=%s params=%s",
                self.table_name,  # type: ignore[attr-defined]
                filters,
                query,
                params,
            )
            raise RepositoryError("Failed to find entities with criteria") from err
        else:
            if result.success:
                return [self._row_to_entity(row) for row in result.rows]  # type: ignore[attr-defined]
            return []

    async def find_one(
        self,
        *filter_expressions: Any,
        columns: list[str] | None = None,
        include_deleted: bool = False,
        **filters: Any,
    ) -> Any:
        """Retrieve the first entity matching *filters*.

        Args:
            columns: Optional column list to select.
            include_deleted: Include soft-deleted rows.
            **filters: Attribute equality (or operator) filters.

        Returns:
            First matching entity or ``None``.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            fields = ", ".join(str(Column(c)) for c in columns) if columns else "*"
            base_query = f"SELECT {fields} FROM {self._table}"  # noqa: S608 -- self._table is a validated Table(); fields are Column()-validated  # type: ignore[attr-defined]
            params: list[Any] = []

            query = await self._apply_filters_to_query(  # type: ignore[attr-defined]
                base_query,
                params,
                filters,
                include_deleted,
                filter_expressions,
            )
            query, params = self._rls_apply(query, params, "SELECT")  # type: ignore[attr-defined]
            query += " LIMIT 1"

            result = await self.provider.execute_query(  # type: ignore[attr-defined]
                query,
                params if params else None,
            )
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
        ) as err:
            logger.exception(
                "Failed find_one table=%s filters=%s",
                self.table_name,  # type: ignore[attr-defined]
                filters,
            )
            raise RepositoryError("Failed to find entity") from err
        else:
            if result.success and result.rows:
                return self._row_to_entity(result.rows[0])  # type: ignore[attr-defined]
            return None

    async def count(
        self, *filter_expressions: Any, include_deleted: bool = False, **filters: Any
    ) -> int:
        """Count entities matching *filters*.

        Args:
            include_deleted: Include soft-deleted rows.
            **filters: Attribute equality (or operator) filters.

        Returns:
            Number of matching entities.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            base_query = f"SELECT COUNT(*) as count FROM {self._table}"  # noqa: S608 -- self._table is a validated Table() identifier  # type: ignore[attr-defined]
            params: list[Any] = []

            query = await self._apply_filters_to_query(  # type: ignore[attr-defined]
                base_query,
                params,
                filters,
                include_deleted,
                filter_expressions,
            )
            query, params = self._rls_apply(query, params, "SELECT")  # type: ignore[attr-defined]

            result = await self.provider.execute_query(query, params)  # type: ignore[attr-defined]
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
        ) as err:
            logger.exception(
                "Failed count table=%s filters=%s",
                self.table_name,  # type: ignore[attr-defined]
                filters,
            )
            raise RepositoryError("Failed to count entities with criteria") from err
        else:
            if result.success and result.rows:
                return int(result.rows[0]["count"])
            return 0

    async def exists(self, include_deleted: bool = False, **filters: Any) -> bool:
        """Check whether any entity matches *filters*.

        Args:
            include_deleted: Include soft-deleted rows.
            **filters: Attribute equality (or operator) filters.

        Returns:
            ``True`` if at least one matching entity exists.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            base_query = f"SELECT COUNT(*) as count FROM {self._table}"  # noqa: S608 -- self._table is a validated Table() identifier  # type: ignore[attr-defined]
            params: list[Any] = []

            query = await self._apply_filters_to_query(  # type: ignore[attr-defined]
                base_query,
                params,
                filters,
                include_deleted,
            )
            query, params = self._rls_apply(query, params, "SELECT")  # type: ignore[attr-defined]

            result = await self.provider.execute_query(  # type: ignore[attr-defined]
                query,
                params if params else None,
            )

            if not result.success:
                raise RepositoryError("Failed to check existence with criteria")

            if not result.rows:
                return False

            return int(result.rows[0].get("count", 0)) > 0
        except RepositoryError:
            raise
        except (
            DatabaseError,
            QueryError,
            DatabaseConnectionError,
            DatabaseTimeoutError,
        ) as err:
            logger.exception(
                "Failed exists table=%s filters=%s",
                self.table_name,  # type: ignore[attr-defined]
                filters,
            )
            raise RepositoryError("Failed to check existence with criteria") from err
