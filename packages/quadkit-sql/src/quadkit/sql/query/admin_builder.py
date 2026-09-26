"""SqlQueryBuilder — immutable fluent builder for constructing SQL WHERE clauses
from admin filter dicts.

Builds a SQLAlchemy ``Select`` and provides ``build()`` to yield the compiled
statement.  Useful for admin data sources that compile raw WHERE text with
dialect-specific parameter styles.
"""

from __future__ import annotations

from typing import Any, Self

from sqlalchemy import Select, UnaryExpression, asc, column, desc, literal, or_, select


class SqlQueryBuilder:
    """Immutable fluent builder wrapping a SQLAlchemy ``Select``.

    Each ``with_*`` method returns a *new* instance — the original is never
    mutated.
    """

    __slots__ = ("_stmt",)

    def __init__(self, stmt: Select | None = None) -> None:
        """Initialise builder, defaulting to ``SELECT _``."""
        self._stmt = stmt if stmt is not None else select(column("_"))

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
        for key, value in filters.items():
            col: Any = column(key)
            if key.endswith("__gte"):
                col_name = key[:-5]
                conditions.append(column(col_name) >= literal(value))
            elif key.endswith("__lte"):
                col_name = key[:-5]
                conditions.append(column(col_name) <= literal(value))
            elif key.endswith("__gt"):
                col_name = key[:-4]
                conditions.append(column(col_name) > literal(value))
            elif key.endswith("__lt"):
                col_name = key[:-4]
                conditions.append(column(col_name) < literal(value))
            else:
                conditions.append(col == literal(value))
        return self.__class__(self._stmt.where(*conditions))

    def with_search(self, search: str, fields: list[str]) -> Self:
        """Add ILIKE search across *fields* joined with OR."""
        if not search or not fields:
            return self
        patterns = [column(f).ilike(f"%{search}%") for f in fields]
        return self.__class__(self._stmt.where(or_(*patterns)))

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
        return self.__class__(self._stmt.order_by(*clauses))

    def with_pagination(self, offset: int, limit: int) -> Self:
        """Add LIMIT and OFFSET."""
        return self.__class__(self._stmt.offset(offset).limit(limit))

    def build(self) -> Select:
        """Return the underlying ``Select`` statement."""
        return self._stmt

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
