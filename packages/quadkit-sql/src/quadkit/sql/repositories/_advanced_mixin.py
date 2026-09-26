"""Advanced mixin for SQLRepository: aggregate, spec queries, cursor pagination, streaming."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from quadkit.contracts.data.identifiers import Column, Table
from quadkit.logging import get_logger
from quadkit.sql.exceptions import (
    DatabaseConnectionError,
    DatabaseError,
    QueryError,
    RepositoryError,
)
from quadkit.sql.repositories.cursor import CursorPage, decode_cursor, encode_cursor

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.sql.specification import SqlSpecification

logger = get_logger(__name__)


class _AdvancedMixin:
    """Provides aggregate queries, specs, cursor pagination, streaming, and bulk ops."""

    _table: Table

    @overload
    async def aggregate(
        self,
        *,
        sum: str | list[str] | None = None,
        avg: str | list[str] | None = None,
        min: str | list[str] | None = None,
        max: str | list[str] | None = None,
        count: str | None = None,
        group_by: None = None,
        **filters: Any,
    ) -> dict[str, Any]: ...
    @overload
    async def aggregate(
        self,
        *,
        sum: str | list[str] | None = None,
        avg: str | list[str] | None = None,
        min: str | list[str] | None = None,
        max: str | list[str] | None = None,
        count: str | None = None,
        group_by: str | list[str],
        **filters: Any,
    ) -> list[dict[str, Any]]: ...
    async def aggregate(
        self,
        *,
        sum: str | list[str] | None = None,
        avg: str | list[str] | None = None,
        min: str | list[str] | None = None,
        max: str | list[str] | None = None,
        count: str | None = None,
        group_by: str | list[str] | None = None,
        **filters: Any,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        """Run aggregate queries using raw SQL.

        Args:
            sum: Column(s) to SUM.
            avg: Column(s) to AVG.
            min: Column(s) to MIN.
            max: Column(s) to MAX.
            count: Column to COUNT (``"*"`` for all rows).
            group_by: Column(s) to GROUP BY.
            **filters: Attribute equality (or operator) filters.

        Returns:
            A single aggregation dict (no ``group_by``) or list of dicts.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            select_parts: list[str] = []

            def _ensure_list(v: str | list[str]) -> list[str]:
                return [v] if isinstance(v, str) else v

            if count is not None:
                safe_count = str(Column(count)) if count != "*" else "*"
                select_parts.append(f"COUNT({safe_count}) AS count")
            elif not any([sum, avg, min, max]):
                select_parts.append("COUNT(*) AS count")

            if sum:
                for col in _ensure_list(sum):
                    sc = Column(col)
                    select_parts.append(f"SUM({sc}) AS {sc.name}_sum")
            if avg:
                for col in _ensure_list(avg):
                    sc = Column(col)
                    select_parts.append(f"AVG({sc}) AS {sc.name}_avg")
            if min:
                for col in _ensure_list(min):
                    sc = Column(col)
                    select_parts.append(f"MIN({sc}) AS {sc.name}_min")
            if max:
                for col in _ensure_list(max):
                    sc = Column(col)
                    select_parts.append(f"MAX({sc}) AS {sc.name}_max")

            group_cols: list[str] = []
            if group_by:
                group_cols = _ensure_list(group_by)
                safe_group_cols = [str(Column(c)) for c in group_cols]
                select_parts = [*safe_group_cols, *select_parts]

            query = f"SELECT {', '.join(select_parts)} FROM {self._table}"  # noqa: S608 -- self._table Table()-validated; select parts Column()-validated
            params: list[Any] = []

            query = await self._apply_filters_to_query(  # type: ignore[attr-defined]
                query,
                params,
                filters,
            )

            if group_cols:
                safe_gc = ", ".join(str(Column(c)) for c in group_cols)
                query += f" GROUP BY {safe_gc}"

            result = await self.provider.execute_query(query, params)  # type: ignore[attr-defined]

            if not result.success:
                raise RepositoryError(
                    f"Aggregate failed: {result.error_message}",
                )

            if group_cols:
                return list(result.rows)
            return dict(result.rows[0]) if result.rows else {}
        except RepositoryError:
            raise
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.exception(
                "Failed aggregate table=%s",
                self.table_name,  # type: ignore[attr-defined]
            )
            raise RepositoryError("Failed to run aggregate query") from err

    async def find_by_spec(
        self,
        spec: SqlSpecification,
        *,
        limit: int | None = None,
        offset: int | None = None,
        sort_by: str | None = None,
        sort_order: str = "asc",
    ) -> list[Any]:
        """Find entities matching a specification.

        Args:
            spec: SQL specification providing a WHERE clause.
            limit: Maximum rows to return.
            offset: Rows to skip.
            sort_by: Column to sort by.
            sort_order: ``"asc"`` or ``"desc"``.

        Returns:
            List of matching entities.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            where_sql, params = spec.to_sql()
            query = f"SELECT * FROM {self._table} WHERE {where_sql}"  # noqa: S608 -- self._table Table()-validated; spec fragments Column()-validated (RawSpecification is documented escape hatch)  # type: ignore[attr-defined]

            if sort_by:
                sort_col = Column(sort_by)
                direction = "DESC" if sort_order.lower() == "desc" else "ASC"
                query += f" ORDER BY {sort_col} {direction}"
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)
            if offset is not None and offset > 0:
                query += " OFFSET ?"
                params.append(offset)

            result = await self.provider.execute_query(query, params)  # type: ignore[attr-defined]
            if result.success:
                return [self._row_to_entity(row) for row in result.rows]  # type: ignore[attr-defined]
            return []
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.exception(
                "Failed find_by_spec table=%s",
                self.table_name,  # type: ignore[attr-defined]
            )
            raise RepositoryError("Failed to find by spec") from err

    async def count_by_spec(self, spec: SqlSpecification) -> int:
        """Count entities matching a specification.

        Args:
            spec: SQL specification providing a WHERE clause.

        Returns:
            Number of matching entities.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            where_sql, params = spec.to_sql()
            query = f"SELECT COUNT(*) AS count FROM {self._table} WHERE {where_sql}"  # noqa: S608 -- self._table Table()-validated; spec fragments Column()-validated (RawSpecification is documented escape hatch)  # type: ignore[attr-defined]
            result = await self.provider.execute_query(query, params)  # type: ignore[attr-defined]
            if result.success and result.rows:
                return int(result.rows[0]["count"])
            return 0
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.exception(
                "Failed count_by_spec table=%s",
                self.table_name,  # type: ignore[attr-defined]
            )
            raise RepositoryError("Failed to count by spec") from err

    async def paginate_cursor(
        self,
        *,
        cursor: str | None = None,
        limit: int = 20,
        sort_by: str = "id",
        sort_order: str = "asc",
        include_total: bool = False,
        **filters: Any,
    ) -> CursorPage[Any]:
        """Cursor-based pagination using keyset pagination.

        Args:
            cursor: Opaque cursor from a previous page response.
            limit: Maximum entities per page.
            sort_by: Column used as the keyset sort key.
            sort_order: ``"asc"`` or ``"desc"``.
            include_total: Whether to compute and include the total count.
            **filters: Attribute equality (or operator) filters.

        Returns:
            :class:`CursorPage` containing items and the next/prev cursors.

        Raises:
            RepositoryError: On database failure.
        """
        try:
            is_desc = sort_order.lower() == "desc"
            direction = "DESC" if is_desc else "ASC"
            op = "<" if is_desc else ">"

            query = f"SELECT * FROM {self._table}"  # noqa: S608 -- self._table Table()-validated  # type: ignore[attr-defined]
            params: list[Any] = []

            # Apply filters
            query = await self._apply_filters_to_query(  # type: ignore[attr-defined]
                query,
                params,
                dict(filters),
            )

            # Apply cursor condition
            if cursor:
                cursor_data = decode_cursor(cursor)
                cursor_value = cursor_data.get(sort_by)
                if cursor_value is not None:
                    has_where = " WHERE " in query.upper()
                    keyword = " AND " if has_where else " WHERE "
                    sort_col = Column(sort_by)
                    query += f"{keyword}{sort_col} {op} ?"
                    params.append(cursor_value)

            sort_col = Column(sort_by)
            query += f" ORDER BY {sort_col} {direction}"
            # Fetch one extra to check has_next
            query += " LIMIT ?"
            params.append(limit + 1)

            result = await self.provider.execute_query(query, params)  # type: ignore[attr-defined]

            if not result.success:
                raise RepositoryError(
                    f"Cursor paginate failed: {result.error_message}",
                )

            rows = result.rows or []
            has_next = len(rows) > limit
            items = [self._row_to_entity(r) for r in rows[:limit]]  # type: ignore[attr-defined]

            # Build next cursor
            next_cursor = None
            if has_next and items:
                last = rows[limit - 1]
                next_cursor = encode_cursor({sort_by: last.get(sort_by)})

            # Build previous cursor
            prev_cursor = None
            if cursor and items:
                first = rows[0]
                prev_cursor = encode_cursor({sort_by: first.get(sort_by)})

            total = None
            if include_total:
                total = await self.count(**filters)  # type: ignore[attr-defined]

            return CursorPage(
                items=items,
                next_cursor=next_cursor,
                prev_cursor=prev_cursor,
                has_more=has_next,
                has_previous=cursor is not None,
                total_count=total,
            )
        except RepositoryError:
            raise
        except (DatabaseError, QueryError, DatabaseConnectionError) as err:
            logger.exception(
                "Failed paginate_cursor table=%s",
                self.table_name,  # type: ignore[attr-defined]
            )
            raise RepositoryError("Failed cursor pagination") from err

    async def paginate(
        self,
        page: int = 1,
        per_page: int = 20,
        **filters: Any,
    ) -> dict[str, Any]:
        """Return paginated results matching *filters*.

        Args:
            page: 1-based page number.
            per_page: Number of results per page.
            **filters: Attribute equality filters forwarded to ``find_many``.

        Returns:
            Dict with ``data``, ``total``, ``page``, ``per_page``,
            ``total_pages`` keys.
        """
        offset = (page - 1) * per_page
        data = await self.find_many(limit=per_page, offset=offset, **filters)  # type: ignore[attr-defined]
        total = await self.count(**filters)  # type: ignore[attr-defined]
        return {
            "data": data,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        }

    async def stream(
        self,
        *,
        batch_size: int = 100,
        sort_by: str | None = None,
        sort_order: str = "asc",
        **filters: Any,
    ) -> AsyncIterator[Any]:
        """Stream all matching entities in batches.

        Args:
            batch_size: Number of entities per batch.
            sort_by: Column to sort by.
            sort_order: ``"asc"`` or ``"desc"``.
            **filters: Attribute equality filters.

        Yields:
            Individual entities in order.
        """
        offset = 0
        while True:
            batch = await self.find_many(  # type: ignore[attr-defined]
                limit=batch_size,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
                **filters,
            )
            if not batch:
                break
            for entity in batch:
                yield entity
            if len(batch) < batch_size:
                break
            offset += batch_size

    async def find_or_create(
        self,
        defaults: dict[str, Any] | None = None,
        **lookup: Any,
    ) -> tuple[Any, bool]:
        """Find entity by *lookup* or create one with *defaults*.

        Args:
            defaults: Additional fields to set on creation (merged with lookup).
            **lookup: Attribute equality filters used for the lookup.

        Returns:
            ``(entity, created)`` tuple where *created* is ``True`` when
            a new entity was inserted.
        """
        existing = await self.find_one(**lookup)  # type: ignore[attr-defined]
        if existing is not None:
            return existing, False
        data = {**lookup, **(defaults or {})}
        entity = self._row_to_entity(data)  # type: ignore[attr-defined]
        created = await self.create(entity)  # type: ignore[attr-defined]
        return created, True

    async def update_or_create(
        self,
        defaults: dict[str, Any] | None = None,
        **lookup: Any,
    ) -> tuple[Any, bool]:
        """Update entity if it exists, otherwise create it.

        Args:
            defaults: Fields to update (merged onto existing entity or new one).
            **lookup: Attribute equality filters used for the lookup.

        Returns:
            ``(entity, created)`` tuple where *created* is ``True`` when
            a new entity was inserted.
        """
        existing = await self.find_one(**lookup)  # type: ignore[attr-defined]
        if existing is not None:
            data = self._entity_to_dict(existing)  # type: ignore[attr-defined]
            data.update(defaults or {})
            updated_entity = self._row_to_entity(data)  # type: ignore[attr-defined]
            result = await self.update(updated_entity)  # type: ignore[attr-defined]
            return result, False
        data = {**lookup, **(defaults or {})}
        entity = self._row_to_entity(data)  # type: ignore[attr-defined]
        created = await self.create(entity)  # type: ignore[attr-defined]
        return created, True

    async def bulk_create(self, entities: list[Any]) -> list[Any]:
        """Create multiple entities sequentially.

        Args:
            entities: Entities to insert.

        Returns:
            List of created entities (with generated IDs populated).
        """
        results = []
        for entity in entities:
            results.append(await self.create(entity))  # type: ignore[attr-defined]
        return results

    async def bulk_update(self, entities: list[Any]) -> list[Any]:
        """Update multiple entities sequentially.

        Args:
            entities: Entities to update.

        Returns:
            List of updated entities.
        """
        results = []
        for entity in entities:
            results.append(await self.update(entity))  # type: ignore[attr-defined]
        return results

    async def bulk_delete(self, keys_or_entities: list[Any]) -> bool:
        """Delete multiple entities sequentially.

        Args:
            keys_or_entities: List of entities or primary key values to delete.

        Returns:
            ``True`` if all deletes succeeded, ``False`` if any failed.
        """
        success = True
        for item in keys_or_entities:
            if not await self.delete(item):  # type: ignore[attr-defined]
                success = False
        return success
