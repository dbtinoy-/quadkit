"""Core mixin for AsyncQueryBuilder: init, DML methods, locking, execute."""

from __future__ import annotations

from typing import Any, ClassVar, Self

from quadkit.contracts.data.identifiers import Column
from quadkit.contracts.data.identifiers import Table as SQLTable
from quadkit.contracts.data.sql.sql_dialect import SQLDialect
from quadkit.sql.query.operators import QueryOperatorRegistry
from quadkit.sql.query.sql_types import (
    Condition,
    ConflictAction,
    CTEClause,
    HavingClause,
    Join,
    LockMode,
    OrCondition,
    Order,
    RawExpression,
    SetOperation,
    WindowExpression,
)


class _CoreMixin:
    """Core init, DML, locking, and execute methods for AsyncQueryBuilder."""

    _operator_registry: ClassVar[QueryOperatorRegistry] = QueryOperatorRegistry()

    def __init__(self, table: str, dialect: SQLDialect = SQLDialect.POSTGRESQL):
        """Initialize the query builder.

        Args:
            table: The table name to query.
            dialect: The SQL dialect. Defaults to PostgreSQL.
        """
        self._table = SQLTable(table)
        self._dialect = dialect
        self._mode = "select"
        self._selects: list[str | Column] = ["*"]
        self._wheres: list[Condition] = []
        self._or_wheres: list[OrCondition] = []
        self._joins: list[Join] = []
        self._orders: list[Order] = []
        self._raw_orders: list[str] = []
        self._limit: int | None = None
        self._offset: int | None = None
        self._data: dict[str, Any] = {}
        self._returning: list[str] = []
        # Phase 1 additions
        self._group_by: list[str | Column] = []
        self._havings: list[HavingClause] = []
        self._raw_selects: list[RawExpression] = []
        self._raw_wheres: list[RawExpression] = []
        self._distinct: bool = False
        self._distinct_on: list[str | Column] = []
        self._conflict_columns: list[str] = []
        self._conflict_action: ConflictAction | None = None
        self._conflict_update_columns: list[str] = []
        self._lock_mode: LockMode | None = None
        self._lock_skip_locked: bool = False
        self._lock_no_wait: bool = False
        # Phase 2 additions
        self._ctes: list[CTEClause] = []
        self._windows: list[WindowExpression] = []
        self._set_operations: list[SetOperation] = []
        self._subquery_wheres: list[RawExpression] = []

    def select(self, *columns: str) -> Self:
        """Set the columns to select.

        Args:
            columns: Column names to select. If empty, selects all (*).

        Returns:
            Self for method chaining.

        Example:
            >>> builder.select("id", "email", "name")
            >>> builder.select()  # Selects all columns
        """
        self._mode = "select"
        if columns:
            self._selects = ["*" if c == "*" else Column(c) for c in columns]
        else:
            self._selects = ["*"]
        return self

    def insert(self, data: dict[str, Any]) -> Self:
        """Set the query mode to INSERT.

        Args:
            data: Dictionary of column-value pairs to insert.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.insert({"email": "user@example.com", "name": "John"})
        """
        self._mode = "insert"
        self._data = {str(Column(col)): value for col, value in data.items()}
        return self

    def update(self, data: dict[str, Any]) -> Self:
        """Set the query mode to UPDATE.

        Args:
            data: Dictionary of column-value pairs to update.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.update({"status": "active"}).where("id", Operator.EQ, 1)
        """
        self._mode = "update"
        self._data = {str(Column(col)): value for col, value in data.items()}
        return self

    def delete(self) -> Self:
        """Set the query mode to DELETE.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.delete().where("id", Operator.EQ, 1)
        """
        self._mode = "delete"
        return self

    def returning(self, *columns: str) -> Self:
        """Add a RETURNING clause for INSERT/UPDATE/DELETE queries.

        Args:
            columns: Column names to return.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.insert(data).returning("id", "created_at")
        """
        self._returning = [str(Column(c)) for c in columns]
        return self

    def order_by(self, column: str, desc: bool = False) -> Self:
        """Add an ORDER BY clause.

        Args:
            column: The column to order by.
            desc: If True, order descending. Defaults to False (ascending).

        Returns:
            Self for method chaining.

        Example:
            >>> builder.order_by("created_at", desc=True)
        """
        self._orders.append(Order(Column(column), desc))
        return self

    def limit(self, n: int) -> Self:
        """Add a LIMIT clause.

        Args:
            n: Maximum number of rows to return.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.limit(10)
        """
        self._limit = n
        return self

    def offset(self, n: int) -> Self:
        """Add an OFFSET clause.

        Args:
            n: Number of rows to skip.

        Returns:
            Self for method chaining.

        Example:
            >>> builder.limit(10).offset(20)  # Skip first 20 rows
        """
        self._offset = n
        return self

    def distinct(self, *columns: str) -> Self:
        """Add DISTINCT to the query.

        Example:
            >>> builder.distinct()  # SELECT DISTINCT ...
            >>> builder.distinct("email")  # SELECT DISTINCT ON (email) ... (PG only)
        """
        self._distinct = True
        if columns:
            self._distinct_on = [Column(c) for c in columns]
        return self

    def on_conflict(self, *conflict_columns: str) -> Self:
        """Specify conflict columns for INSERT ... ON CONFLICT.

        Example:
            >>> builder.insert(data).on_conflict("email").do_update("name", "updated_at")
        """
        self._conflict_columns = [str(Column(c)) for c in conflict_columns]
        return self

    def do_update(self, *update_columns: str) -> Self:
        """Set ON CONFLICT ... DO UPDATE SET for specified columns.

        Example:
            >>> builder.insert(data).on_conflict("email").do_update("name", "updated_at")
        """
        self._conflict_action = ConflictAction.DO_UPDATE
        self._conflict_update_columns = (
            [str(Column(c)) for c in update_columns] if update_columns else []
        )
        return self

    def do_nothing(self) -> Self:
        """Set ON CONFLICT ... DO NOTHING.

        Example:
            >>> builder.insert(data).on_conflict("email").do_nothing()
        """
        self._conflict_action = ConflictAction.DO_NOTHING
        return self

    def for_update(self, *, skip_locked: bool = False, no_wait: bool = False) -> Self:
        """Add FOR UPDATE row lock.

        Example:
            >>> builder.select("*").where("id", Operator.EQ, 1).for_update()
            >>> builder.select("*").where("status", Operator.EQ, "pending").for_update(skip_locked=True)
        """
        self._lock_mode = LockMode.FOR_UPDATE
        self._lock_skip_locked = skip_locked
        self._lock_no_wait = no_wait
        return self

    def for_share(self) -> Self:
        """Add FOR SHARE row lock."""
        self._lock_mode = LockMode.FOR_SHARE
        return self

    async def execute(self, conn: Any) -> Any:
        """Execute the query using the provided connection.

        Args:
            conn: An async database connection with fetch/execute methods.

        Returns:
            Query results (depends on query mode).
        """
        query = self.build()  # type: ignore[attr-defined]
        if self._mode == "select" or self._returning:
            return await conn.fetch(query.sql, *query.params)
        return await conn.execute(query.sql, *query.params)

    async def execute_one(self, conn: Any) -> dict[str, Any] | None:
        """Execute and return a single row.

        Args:
            conn: An async database connection with fetchrow method.

        Returns:
            Single row as dict, or None.
        """
        query = self.build()  # type: ignore[attr-defined]
        row = await conn.fetchrow(query.sql, *query.params)
        return dict(row) if row else None

    async def execute_scalar(self, conn: Any) -> Any:
        """Execute and return a single scalar value.

        Args:
            conn: An async database connection with fetchval method.

        Returns:
            Single scalar value.
        """
        query = self.build()  # type: ignore[attr-defined]
        return await conn.fetchval(query.sql, *query.params)
