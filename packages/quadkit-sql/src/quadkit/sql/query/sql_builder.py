"""Query builder for constructing type-safe SQL queries.

This module provides a fluent query builder for constructing SQL queries
programmatically. It supports multiple SQL dialects, parameterized queries
to prevent SQL injection, and chainable method calls.

Example:
    Building a SELECT query::

        from quadkit.sql.query import AsyncQueryBuilder, Operator

        builder = AsyncQueryBuilder("users", dialect="postgresql")
        query = (
            builder
            .select("id", "email", "name")
            .where("active", Operator.EQ, True)
            .where("role", Operator.IN, ["admin", "moderator"])
            .order_by("created_at", desc=True)
            .limit(10)
            .build()
        )

        # query.sql: SELECT id, email, name FROM users WHERE active = $1 AND role IN ($2, $3) ORDER BY created_at DESC LIMIT $4
        # query.params: (True, 'admin', 'moderator', 10)

    Building an INSERT query::

        from quadkit.sql.query import AsyncQueryBuilder

        builder = AsyncQueryBuilder("users")
        query = (
            builder
            .insert({"email": "user@example.com", "name": "John"})
            .returning("id", "created_at")
            .build()
        )
"""

from __future__ import annotations

from quadkit.contracts.data.sql.sql_dialect import SQLDialect
from quadkit.sql.query._sql_build_mixin import _BuildMixin
from quadkit.sql.query._sql_core_mixin import _CoreMixin
from quadkit.sql.query._sql_join_aggregate_mixin import _JoinAggregateMixin
from quadkit.sql.query._sql_where_mixin import _WhereMixin

__all__ = ["AsyncQueryBuilder", "SQLDialect"]


class AsyncQueryBuilder(_CoreMixin, _WhereMixin, _JoinAggregateMixin, _BuildMixin):
    """Async-native query builder simplified for common use cases.

    Provides a fluent interface for building SELECT, INSERT, UPDATE, and
    DELETE queries with support for conditions, joins, ordering, and limits.

    Example:
        Building a SELECT query::

            builder = AsyncQueryBuilder("users", dialect="postgresql")
            query = (
                builder
                .select("id", "email")
                .where("status", Operator.EQ, "active")
                .order_by("created_at", desc=True)
                .limit(10)
                .build()
            )

        Building an INSERT query::

            builder = AsyncQueryBuilder("users")
            query = builder.insert({"email": "test@example.com"}).build()
    """
