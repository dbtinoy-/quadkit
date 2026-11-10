"""SqlQueryBuilder — immutable fluent builder for constructing SQL WHERE clauses
from admin filter dicts.

Builds a SQLAlchemy ``Select`` and provides ``build()`` to yield the compiled
statement, plus ``compile_postgres_where()`` for asyncpg-style ``$1, $2, ...``
parameterized ``WHERE`` fragments without leaking SQLAlchemy dialects into
application code.
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any, Self

from sqlalchemy import Select, UnaryExpression, asc, column, desc, literal, or_, select
from sqlalchemy.dialects import postgresql as _pg_dialect


class SqlQueryBuilder:
    """Immutable fluent builder wrapping a SQLAlchemy ``Select``.

    Each ``with_*`` method returns a *new* instance — the original is never
    mutated.
    """

    __slots__ = ("_referenced_columns", "_stmt")

    def __init__(
        self,
        stmt: Select | None = None,
        *,
        referenced_columns: frozenset[str] = frozenset(),
    ) -> None:
        """Initialise builder, defaulting to ``SELECT _``."""
        self._stmt = stmt if stmt is not None else select(column("_"))
        self._referenced_columns = referenced_columns

    # ------------------------------------------------------------------
    # Public builder methods
    # ------------------------------------------------------------------

    def with_filters(self, filters: dict[str, Any]) -> Self:
        """Add WHERE conditions from a filter dict.

        Supported operators (suffixes): ``__gte``, ``__lte``, ``__gt``,
        ``__lt``.  Bare keys (no suffix) produce equality.
        """
        if not filters:
            return self
        conditions: list[Any] = []
        cols: set[str] = set(self._referenced_columns)
        for key, value in filters.items():
            if key.endswith("__gte"):
                col_name = key[:-5]
                cols.add(col_name)
                conditions.append(column(col_name) >= literal(value))
            elif key.endswith("__lte"):
                col_name = key[:-5]
                cols.add(col_name)
                conditions.append(column(col_name) <= literal(value))
            elif key.endswith("__gt"):
                col_name = key[:-4]
                cols.add(col_name)
                conditions.append(column(col_name) > literal(value))
            elif key.endswith("__lt"):
                col_name = key[:-4]
                cols.add(col_name)
                conditions.append(column(col_name) < literal(value))
            else:
                cols.add(key)
                conditions.append(column(key) == literal(value))
        return self.__class__(
            self._stmt.where(*conditions),
            referenced_columns=frozenset(cols),
        )

    def with_search(self, search: str, fields: list[str]) -> Self:
        """Add ILIKE search across *fields* joined with OR."""
        if not search or not fields:
            return self
        patterns = [column(f).ilike(f"%{search}%") for f in fields]
        cols = self._referenced_columns | frozenset(fields)
        return self.__class__(
            self._stmt.where(or_(*patterns)),
            referenced_columns=cols,
        )

    def with_order(self, order: list[tuple[str, str]]) -> Self:
        """Add ORDER BY from *(column, direction)* tuples.

        Direction is ``"asc"`` or ``"desc"`` (case-insensitive).
        """
        if not order:
            return self
        clauses: list[UnaryExpression] = []
        for col_name, direction in order:
            c: Any = column(col_name)
            if direction.lower() == "desc":
                clauses.append(desc(c))
            else:
                clauses.append(asc(c))
        return self.__class__(
            self._stmt.order_by(*clauses),
            referenced_columns=self._referenced_columns,
        )

    def with_pagination(self, offset: int, limit: int) -> Self:
        """Add LIMIT and OFFSET."""
        return self.__class__(
            self._stmt.offset(offset).limit(limit),
            referenced_columns=self._referenced_columns,
        )

    def build(self) -> Select:
        """Return the underlying ``Select`` statement."""
        return self._stmt

    def compile_postgres_where(
        self,
        *,
        table_alias: str | None = None,
        column_names: Iterable[str] = (),
        uuid_text_fields: Iterable[str] = (),
    ) -> tuple[str, list[Any], int]:
        """Compile the ``WHERE`` predicate to PostgreSQL ``$1, $2, ...`` SQL.

        Args:
            table_alias: Optional SQL table alias (e.g. ``"a"``) applied to
                referenced column identifiers for ``JOIN`` queries.
            column_names: Extra column identifiers to qualify when
                *table_alias* is provided.
            uuid_text_fields: UUID columns requiring an explicit ``::text``
                cast before ``ILIKE`` predicates.

        Returns:
            ``(where_sql, params, next_param_index)`` where ``where_sql``
            omits the leading ``WHERE `` keyword (empty string when no
            predicates are present).
        """
        if self._stmt.whereclause is None:
            return "", [], 1

        compiled = self._stmt.compile(dialect=_pg_dialect.dialect(paramstyle="numeric"))
        sql_text = str(compiled)
        where_idx = sql_text.upper().find("WHERE ")
        if where_idx == -1:
            return "", [], 1

        where_str = re.sub(r":(\d+)", r"$\1", sql_text[where_idx + 6 :])

        all_cols = set(self._referenced_columns) | set(column_names)
        if table_alias and all_cols:
            for col in sorted(all_cols, key=len, reverse=True):
                where_str = re.sub(
                    r"(?<![.\w])"
                    + re.escape(col)
                    + r"(?=\s*(?:>=|<=|>|<|!=|=|ILIKE|LIKE|IS|IN|\)|\$|\sOR|\sAND|$))",
                    f"{table_alias}.{col}",
                    where_str,
                )

        prefix = f"{table_alias}." if table_alias else ""
        for field in uuid_text_fields:
            where_str = where_str.replace(
                f"{prefix}{field} ILIKE",
                f"{prefix}{field}::text ILIKE",
            )

        params = list(compiled.params.values())
        return where_str, params, len(params) + 1

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_params(
        cls,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        search_fields: list[str] | None = None,
        order: list[tuple[str, str]] | None = None,
        offset: int | None = None,
        limit: int | None = None,
    ) -> SqlQueryBuilder:
        """Create a builder from admin query parameters.

        Parameters are applied in the natural order: filters → search → order
        → pagination.
        """
        builder = cls()
        if filters:
            builder = builder.with_filters(filters)
        if search and search_fields:
            builder = builder.with_search(search, search_fields)
        if order:
            builder = builder.with_order(order)
        if offset is not None and limit is not None:
            builder = builder.with_pagination(offset, limit)
        return builder
