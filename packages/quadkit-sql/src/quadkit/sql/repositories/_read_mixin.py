"""Read mixin for SQLRepository: find_by_id, find_many, find_one, count, exists."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from quadkit.contracts.data.identifiers import Column, Table
from quadkit.contracts.data.sql.database import provider_dialect
from quadkit.logging import get_logger, safe_error_type
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    DatabaseTimeoutError,
    QueryError,
    RepositoryError,
)

logger = get_logger(__name__)

#: Dialects that implement ``SELECT … FOR UPDATE`` with the ANSI spelling.
#:
#: SQLite has no row locks — it serializes writers for the whole database — so
#: asking it to lock is meaningless and, as raw text, a syntax error. That is
#: why the clause is dialect-gated here instead of always appended: a caller
#: that needs the lock on Postgres/MySQL must not break the default SQLite host,
#: which is the deployment the framework's own tests run against.
_LOCKING_DIALECTS = frozenset({"postgres", "postgresql", "mysql", "mariadb", "oracle"})


def _lock_clause(provider: Any, lock: bool) -> str:
    """Return the row-lock clause for *provider*, or ``""``.

    Args:
        provider: The repository's ``DatabaseProviderProtocol``.
        lock: Whether the caller asked for a row lock.

    Returns:
        ``" FOR UPDATE"`` on a dialect that supports it, otherwise an empty
        string — SQLite rejects the clause outright.
    """
    if not lock:
        return ""
    return " FOR UPDATE" if provider_dialect(provider) in _LOCKING_DIALECTS else ""


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
            logger.error(
                "repository_find_by_id_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to find entity") from err
        else:
            if result.success and result.rows:
                return self._row_to_entity(result.rows[0])  # type: ignore[attr-defined]
            return None

    async def find_many(
        self,
        *filter_expressions: Any,
        limit: int | None = None,
        offset: int | None = 0,
        sort_by: str | Sequence[str] | None = None,
        sort_order: str | Sequence[str] = "asc",
        allowed_sort_fields: list[str] | None = None,
        columns: list[str] | None = None,
        include_deleted: bool = False,
        lock: bool = False,
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
            lock: Take a row lock (``SELECT ... FOR UPDATE``) on the rows read.
                Only meaningful inside a transaction — the lock lives exactly
                as long as it does. Ignored on dialects that cannot express it
                (SQLite, where the database serializes writers anyway).
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
            order_by = self._order_by_clause(sort_by, sort_order, allowed_sort_fields)
            if order_by:
                query += f" ORDER BY {order_by}"

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        if offset and offset > 0:
            query += " OFFSET ?"
            params.append(offset)

        query += _lock_clause(self.provider, lock)  # type: ignore[attr-defined]

        try:
            logger.debug(
                "Executing find_many on %s: %s",
                getattr(self.provider, "name", "unknown"),  # type: ignore[attr-defined]
                len(params),
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
            logger.error(
                "repository_find_many_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to find entities with criteria") from err
        else:
            if result.success:
                return [self._row_to_entity(row) for row in result.rows]  # type: ignore[attr-defined]
            return []

    @staticmethod
    def _order_by_clause(
        sort_by: str | Sequence[str],
        sort_order: str | Sequence[str],
        allowed_sort_fields: list[str] | None,
    ) -> str:
        """Render one ``ORDER BY`` spanning *sort_by*'s columns.

        A single column is the common case, but a tie-break is not optional
        when the leading column is not unique: a scheduler's system tasks store
        ``created_at`` in whole seconds, so two runs of the same job routinely
        share one and the insertion order (``id``) is what "newest" means.
        Without a second key such a read silently answers with the older row.

        Args:
            sort_by: Column name, or columns in precedence order.
            sort_order: One direction for every column, or one per column.
            allowed_sort_fields: Whitelist of sortable columns; raises when a
                requested column is not in it.

        Returns:
            The ``ORDER BY`` body, or ``""`` when *sort_by* is empty.

        Raises:
            RepositoryError: When a column is not in *allowed_sort_fields*, or
                the direction list has the wrong length or an unknown value.
        """
        columns: tuple[str, ...] = (
            (sort_by,) if isinstance(sort_by, str) else tuple(sort_by)
        )
        columns = tuple(column for column in columns if column)
        if not columns:
            return ""
        if allowed_sort_fields:
            for column in columns:
                if column not in allowed_sort_fields:
                    raise RepositoryError(
                        f"Sorting by '{column}' is not allowed. Allowed fields: {allowed_sort_fields}",
                    )

        if isinstance(sort_order, str):
            directions = [sort_order] * len(columns)
        else:
            directions = list(sort_order)
            if len(directions) == 1:
                directions *= len(columns)
            elif len(directions) != len(columns):
                raise RepositoryError(
                    f"sort_order has {len(directions)} entries for {len(columns)} sort columns",
                )

        rendered: list[str] = []
        for column, direction in zip(columns, directions, strict=True):
            if direction.lower() not in {"asc", "desc"}:
                raise RepositoryError(
                    f"sort_order must be 'asc' or 'desc', got {direction!r}"
                )
            rendered.append(
                f"{Column(column)} {'DESC' if direction.lower() == 'desc' else 'ASC'}"
            )
        return ", ".join(rendered)

    async def find_one(
        self,
        *filter_expressions: Any,
        columns: list[str] | None = None,
        include_deleted: bool = False,
        lock: bool = False,
        **filters: Any,
    ) -> Any:
        """Retrieve the first entity matching *filters*.

        Args:
            columns: Optional column list to select.
            include_deleted: Include soft-deleted rows.
            lock: Take a row lock (``SELECT ... FOR UPDATE``) on the row read.
                Only meaningful inside a transaction — the lock lives exactly
                as long as it does. Ignored on dialects that cannot express it
                (SQLite, where the database serializes writers anyway).
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
            query += _lock_clause(self.provider, lock)  # type: ignore[attr-defined]

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
            logger.error(
                "repository_find_one_failed",
                error_type=safe_error_type(err),
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
            logger.error(
                "repository_count_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to count entities with criteria") from err
        else:
            if result.success and result.rows:
                return int(result.rows[0]["count"])
            return 0

    async def exists(
        self, *filter_expressions: Any, include_deleted: bool = False, **filters: Any
    ) -> bool:
        """Check whether any entity matches *filters*.

        Args:
            *filter_expressions: Typed ``Filter`` expressions to AND together —
                the same ones ``find_many`` and ``count`` accept. Without them
                an "is there an active subscription" check that needs an
                operator (``IN``, ``IS NULL``) could not ask the question at
                all, and callers fell back to fetching rows to test emptiness.
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
                filter_expressions,
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
            logger.error(
                "repository_exists_failed",
                error_type=safe_error_type(err),
            )
            raise RepositoryError("Failed to check existence with criteria") from err
