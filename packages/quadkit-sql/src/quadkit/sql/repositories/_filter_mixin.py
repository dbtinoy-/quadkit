"""Filter mixin for SQLRepository: ``_apply_filters_to_query``."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar

from quadkit.contracts.data.identifiers import Column
from quadkit.logging import get_logger
from quadkit.sql.exceptions import TenantScopingError
from quadkit.sql.lib import parse_date_safely
from quadkit.sql.repositories.filter_objects import normalize_filters
from quadkit.sql.repositories.filters import FilterOperatorRegistry

logger = get_logger(__name__)


class _FilterMixin:
    """Provides ``_apply_filters_to_query`` for SQL repositories."""

    _filter_registry: ClassVar[FilterOperatorRegistry] = (
        FilterOperatorRegistry.with_defaults()
    )

    async def _apply_filters_to_query(
        self,
        query: str,
        params: list[Any],
        filters: dict[str, Any],
        include_deleted: bool = False,
        filter_expressions: tuple[Any, ...] = (),
    ) -> str:
        """Helper to apply search and sophisticated filters to a SQL query."""
        search_term = filters.pop("search", None)
        search_fields = filters.pop("search_fields", [])

        where_parts = []

        if self.soft_delete_enabled and not include_deleted:  # type: ignore[attr-defined]
            where_parts.append("deleted_at IS NULL")

        for typed_filter in normalize_filters(filter_expressions):
            where_part, filter_params = typed_filter.to_sql()
            where_parts.append(where_part)
            params.extend(filter_params)

        for field_spec, value in filters.items():

            def _std(v: Any) -> Any:
                if isinstance(v, list):
                    return list(map(_std, v))
                if isinstance(v, str):
                    lower_v = v.lower()
                    if lower_v in ("on", "true"):
                        return True
                    if lower_v in ("off", "false"):
                        return False
                return v

            check_val = value[0] if isinstance(value, list) and value else value
            parsed_check = parse_date_safely(check_val)
            if isinstance(parsed_check, (date, datetime)) or any(
                d in field_spec
                for d in [
                    "date",
                    "time",
                    "created_at",
                    "updated_at",
                    "deleted_at",
                    "last_active",
                ]
            ):
                logger.info(
                    "Skipping date-related filter in query: %s=%s",
                    field_spec,
                    value,
                )
                continue

            if "__" in field_spec:
                raw_field, op = field_spec.split("__", 1)
                field = str(Column(raw_field))
                where_part, new_params = self._filter_registry.apply_operator(
                    op,
                    field,
                    value,
                    params,
                )
                # Handlers return a *new* list (copy-on-append); extend the
                # caller's list in place so the bound values are not lost.
                params.extend(new_params[len(params) :])
                where_parts.append(where_part)
            else:
                safe_field = str(Column(field_spec))
                where_parts.append(f"{safe_field} = ?")
                params.append(_std(check_val))

        if search_term and search_fields:
            search_clause = " OR ".join(
                f"{Column(field)} ILIKE ?" for field in search_fields
            )
            where_parts.append(f"({search_clause})")
            params.extend([f"%{search_term}%" for _ in search_fields])
            logger.info(
                "search.apply_ilike",
                search_term=search_term,
                search_fields=list(search_fields),
                clause=search_clause,
            )

        if self.multi_tenant:  # type: ignore[attr-defined]
            tenant_id = self._db_ctx.tenant_id if self._db_ctx is not None else None  # type: ignore[attr-defined]
            if tenant_id:
                where_parts.append("tenant_id = ?")
                params.append(tenant_id)
            else:
                raise TenantScopingError(
                    table=self.table_name,  # type: ignore[attr-defined]
                    operation="SELECT",
                )

        if where_parts:
            keyword = " AND " if _has_top_level_where(query) else " WHERE "
            query += keyword + " AND ".join(where_parts)

        return query


def _has_top_level_where(query: str) -> bool:
    """Return ``True`` when *query* already contains a top-level WHERE.

    A WHERE inside a parenthesised subquery/derived table does not count:
    ``SELECT * FROM (SELECT * FROM t WHERE a = 1) x`` has no top-level
    WHERE, while ``SELECT * FROM t WHERE (a = 1)`` does.  The old
    last-paren heuristic produced a second ``WHERE`` keyword in the latter
    case (invalid SQL) and would have dropped the ``AND`` in a query whose
    WHERE sits after a parenthesised select list.
    """
    upper = query.upper()
    marker = " WHERE "
    depth = 0
    for i, ch in enumerate(upper):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and upper.startswith(marker, i):
            return True
    return False
