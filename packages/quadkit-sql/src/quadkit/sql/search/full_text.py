"""Dialect-aware full-text search helpers for GenericRepository.

Supports PostgreSQL ``to_tsvector``/``to_tsquery`` and MySQL ``MATCH … AGAINST``
full-text search.  Raw SQL is used intentionally so that users are not forced to
declare model-level FTS indexes in their ORM mappings.
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum
import re
from typing import TYPE_CHECKING, Any, SupportsIndex, TypeVar, overload

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts import DatabaseProviderProtocol

logger = get_logger(__name__)

TEntity = TypeVar("TEntity")

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_filter_key(key: str) -> str:
    """Return *key* when it is a plain SQL identifier, else raise.

    ``extra_filters`` keys are interpolated into the WHERE clause, so the
    key must be a bare column identifier and never a raw SQL fragment.

    Raises:
        ValueError: When the key is not a valid identifier.
    """

    if _SAFE_IDENTIFIER.fullmatch(key) is None:
        raise ValueError(f"extra_filters keys must be column identifiers, got {key!r}")
    return key


class FTSDialect(StrEnum):
    """Supported full-text search dialects."""

    POSTGRES = "postgres"
    MYSQL = "mysql"


@dataclasses.dataclass(frozen=True)
class FTSResult(list):
    """Thin wrapper around a list of entities that attaches FTS metadata.

    Attributes:
        items: Matched entities in relevance order.
        total: Total number of results *before* limit/offset (if available).
        dialect: The SQL dialect used for the search.
    """

    items: list[Any]
    total: int
    dialect: FTSDialect

    # Make the list interface work transparently.
    def __iter__(self) -> Any:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @overload
    def __getitem__(self, index: SupportsIndex, /) -> Any: ...

    @overload
    def __getitem__(
        self,
        index: slice[SupportsIndex | None, SupportsIndex | None, SupportsIndex | None],
        /,
    ) -> list[Any]: ...

    def __getitem__(
        self,
        index: SupportsIndex
        | slice[SupportsIndex | None, SupportsIndex | None, SupportsIndex | None],
        /,
    ) -> Any:
        return self.items[index]


class PostgresFTSQuery:
    """Builds PostgreSQL full-text search queries.

    Uses ``to_tsvector`` (GIN index friendly) and ``to_tsquery`` / ``plainto_tsquery``
    depending on *plain* mode.

    Attributes:
        table: Table name to search.
        columns: List of column names to include in the tsvector.
        config: PostgreSQL text search configuration (e.g. ``'english'``).
        plain: When ``True`` uses ``plainto_tsquery`` which is safer for
            user-supplied input (no operator syntax needed).
    """

    def __init__(
        self,
        table: str,
        columns: list[str],
        config: str = "english",
        plain: bool = True,
    ) -> None:
        if _SAFE_IDENTIFIER.fullmatch(table) is None:
            raise ValueError(f"table must be a plain SQL identifier, got {table!r}")
        for col in columns:
            if _SAFE_IDENTIFIER.fullmatch(col) is None:
                raise ValueError(f"columns must be plain SQL identifiers, got {col!r}")
        self.table = table
        self.columns = columns
        self.config = config
        self.plain = plain

    def build(
        self,
        query: str,
        extra_filters: dict[str, Any] | None = None,
        limit: int | None = 50,
        offset: int = 0,
    ) -> tuple[str, list[Any]]:
        """Return ``(sql, params)`` ready for ``provider.execute_query``.

        Args:
            query: The search terms supplied by the user.
            extra_filters: Optional equality filters applied as ``AND`` clauses.
            limit: Maximum rows to return.
            offset: Row offset for pagination.

        Returns:
            A tuple of the SQL string and positional parameters.
        """
        tsvector_expr = " || ' ' || ".join(
            f"coalesce({col}::text, '')" for col in self.columns
        )
        ts_fn = "plainto_tsquery" if self.plain else "to_tsquery"
        params: list[Any] = [self.config, query]

        where_parts = [
            f"to_tsvector($1, {tsvector_expr}) @@ {ts_fn}($1, $2)",
        ]

        if extra_filters:
            for key, value in extra_filters.items():
                params.append(value)
                where_parts.append(f"{_safe_filter_key(key)} = ${len(params)}")

        where_clause = " AND ".join(where_parts)
        rank_expr = f"ts_rank(to_tsvector($1, {tsvector_expr}), {ts_fn}($1, $2))"

        sql = (
            f"SELECT *, {rank_expr} AS _fts_rank"  # noqa: S608 -- table/columns validated at construction
            f" FROM {self.table}"
            f" WHERE {where_clause}"
            f" ORDER BY _fts_rank DESC"
        )

        if limit is not None:
            params.append(limit)
            sql += f" LIMIT ${len(params)}"
        if offset:
            params.append(offset)
            sql += f" OFFSET ${len(params)}"

        logger.debug(
            "PostgresFTSQuery.build",
            extra={"table": self.table, "query": query, "plain": self.plain},
        )
        return sql, params


class MySQLFTSQuery:
    """Builds MySQL ``MATCH … AGAINST`` full-text search queries.

    Requires a ``FULLTEXT`` index on *columns* for non-keyword queries.

    Attributes:
        table: Table name to search.
        columns: List of column names included in the FULLTEXT index.
        boolean_mode: When ``True`` uses ``IN BOOLEAN MODE``; otherwise
            uses natural language mode.
    """

    def __init__(
        self,
        table: str,
        columns: list[str],
        boolean_mode: bool = False,
    ) -> None:
        if _SAFE_IDENTIFIER.fullmatch(table) is None:
            raise ValueError(f"table must be a plain SQL identifier, got {table!r}")
        for col in columns:
            if _SAFE_IDENTIFIER.fullmatch(col) is None:
                raise ValueError(f"columns must be plain SQL identifiers, got {col!r}")
        self.table = table
        self.columns = columns
        self.boolean_mode = boolean_mode

    def build(
        self,
        query: str,
        extra_filters: dict[str, Any] | None = None,
        limit: int | None = 50,
        offset: int = 0,
    ) -> tuple[str, list[Any]]:
        """Return ``(sql, params)`` ready for ``provider.execute_query``.

        Args:
            query: The search terms supplied by the user.
            extra_filters: Optional equality filters applied as ``AND`` clauses.
            limit: Maximum rows to return.
            offset: Row offset for pagination.

        Returns:
            A tuple of the SQL string and positional parameters.
        """
        cols_csv = ", ".join(self.columns)
        mode_suffix = " IN BOOLEAN MODE" if self.boolean_mode else ""
        params: list[Any] = [query]

        match_expr = f"MATCH({cols_csv}) AGAINST (%s{mode_suffix})"
        where_parts = [match_expr]

        if extra_filters:
            for key, value in extra_filters.items():
                params.append(value)
                where_parts.append(f"{_safe_filter_key(key)} = %s")

        where_clause = " AND ".join(where_parts)

        sql = (
            f"SELECT *, {match_expr} AS _fts_score"  # noqa: S608 -- table/columns validated at construction
            f" FROM {self.table}"
            f" WHERE {where_clause}"
            f" ORDER BY _fts_score DESC"
        )

        if limit is not None:
            params.append(limit)
            sql += " LIMIT %s"
        if offset:
            params.append(offset)
            sql += " OFFSET %s"

        logger.debug(
            "MySQLFTSQuery.build",
            extra={
                "table": self.table,
                "query": query,
                "boolean_mode": self.boolean_mode,
            },
        )
        return sql, params


async def full_text_search(
    *,
    provider: DatabaseProviderProtocol,
    table: str,
    columns: list[str],
    query: str,
    dialect: FTSDialect | str = FTSDialect.POSTGRES,
    entity_class: type[TEntity] | None = None,
    extra_filters: dict[str, Any] | None = None,
    limit: int | None = 50,
    offset: int = 0,
    postgres_config: str = "english",
    postgres_plain: bool = True,
    mysql_boolean_mode: bool = False,
) -> FTSResult:
    """Dialect-agnostic full-text search helper.

    Builds and executes the appropriate FTS query using *provider*.

    Args:
        provider: The active database provider used to execute queries.
        table: Table name to search.
        columns: Columns to include in the full-text index / tsvector.
        query: User-supplied search string.
        dialect: Which SQL dialect to use (``"postgres"`` or ``"mysql"``).
        entity_class: Optional class to deserialise rows into.  When
            ``None`` raw ``dict`` rows are returned.
        extra_filters: Additional equality filters (``AND`` clauses).
        limit: Maximum rows to return.
        offset: Row offset for pagination.
        postgres_config: PostgreSQL text search configuration.
        postgres_plain: Use ``plainto_tsquery`` when ``True``.
        mysql_boolean_mode: Use MySQL boolean mode when ``True``.

    Returns:
        :class:`FTSResult` containing matched items (deserialised when
        *entity_class* is provided) and the result count.

    Raises:
        ValueError: When an unsupported *dialect* is given.
    """
    dialect = FTSDialect(dialect)

    if dialect is FTSDialect.POSTGRES:
        builder: PostgresFTSQuery | MySQLFTSQuery = PostgresFTSQuery(
            table=table,
            columns=columns,
            config=postgres_config,
            plain=postgres_plain,
        )
    elif dialect is FTSDialect.MYSQL:
        builder = MySQLFTSQuery(
            table=table,
            columns=columns,
            boolean_mode=mysql_boolean_mode,
        )
    else:  # pragma: no cover  - enum exhaustion guard
        raise ValueError(f"Unsupported FTS dialect: {dialect!r}")

    sql, params = builder.build(
        query=query,
        extra_filters=extra_filters,
        limit=limit,
        offset=offset,
    )

    logger.info(
        "full_text_search executing",
        extra={"table": table, "dialect": dialect.value, "query": query},
    )

    rows: list[dict[str, Any]] = await provider.execute_query(sql, params)  # type: ignore[assignment]

    if entity_class is not None and entity_class is not dict:
        from quadkit.domain import DomainModel

        def _deserialise(row: dict[str, Any]) -> Any:
            # Remove the synthetic rank/score column before deserialising
            clean = {k: v for k, v in row.items() if not k.startswith("_fts_")}
            if issubclass(entity_class, DomainModel):
                return entity_class.model_validate(clean)
            return entity_class(**clean)

        items: list[Any] = [_deserialise(row) for row in rows]
    else:
        items = [
            {k: v for k, v in row.items() if not k.startswith("_fts_")} for row in rows
        ]

    return FTSResult(items=items, total=len(items), dialect=dialect)
