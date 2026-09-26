"""Query building and compilation utilities.

`quadkit.sql.query` now hosts both SQL query layers:

1. The domain-level immutable query model (`Query`, `QueryBuilder`,
   `SearchQueryBuilder`, `PredicateCompiler`)
2. The SQL-rendering layer (`AsyncQueryBuilder`, `Operator`, and related SQL
   builder types)

The domain layer expresses *what* to query. The SQL builder layer renders
that intent into dialect-specific SQL for PostgreSQL, MySQL, and SQLite.
"""

from __future__ import annotations

from quadkit.sql.query.admin_builder import SqlQueryBuilder
from quadkit.sql.query.builder import Query, QueryBuilder, SearchQueryBuilder
from quadkit.sql.query.compiler import Predicate, PredicateCompiler
from quadkit.sql.query.cursor import CursorCodec
from quadkit.sql.query.operators import Operator, QueryOperator, QueryOperatorRegistry
from quadkit.sql.query.sql_builder import AsyncQueryBuilder, SQLDialect

__all__ = [
    "AsyncQueryBuilder",
    "CursorCodec",
    "Operator",
    "Predicate",
    "PredicateCompiler",
    "Query",
    "QueryBuilder",
    "QueryOperator",
    "QueryOperatorRegistry",
    "SQLDialect",
    "SearchQueryBuilder",
    "SqlQueryBuilder",
]
