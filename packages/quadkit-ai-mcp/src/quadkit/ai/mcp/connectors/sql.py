"""Safe parameterized SQL connector — exposes table queries as MCP tools.

Unlike the legacy ``DatabaseResourceProvider`` (which had an SQL injection
vulnerability), this connector:

- Enforces an explicit table allowlist
- Uses fully qualified identifier quoting for table names
- Passes all user-supplied values via ``$N`` parameters (never f-string)
- Restricts filters to allowlisted columns and a closed operator set
- Restricts to SELECT only when ``read_only=True`` (the default)

Tools exposed:
- ``sql_query``           — Execute a read-only SELECT against an allowed table
- ``sql_list_tables``     — List all tables in the allowlist
- ``sql_describe_table``  — Return column names and types for an allowed table
"""

from __future__ import annotations

import re
from typing import Any

from quadkit.ai.mcp.types import MCPResource, MCPToolDefinition, MCPToolResult
from quadkit.contracts.data.identifiers import Column
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)

# Allowlist pattern: table names must be identifiers only (no operators/quotes)
_SAFE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Closed operator set for structured filters
_FILTER_OPS: dict[str, str] = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "in": "IN",
}


class SQLConnector:
    """Safe parameterized SQL connector for MCP.

    Exposes ``DatabaseProviderProtocol``-backed read operations as MCP tools.
    All public methods guard against SQL injection by:
    1. Validating table names against an explicit allowlist.
    2. Quoting identifiers using ``"`` (ANSI standard, supported by all major RDBMS).
    3. Never interpolating user values — only ``$N`` placeholders are used.

    Example::

        connector = SQLConnector(
            db=database_provider,
            allowed_tables=["orders", "customers"],
        )
    """

    def __init__(
        self,
        db: Any,
        allowed_tables: list[str],
        *,
        read_only: bool = True,
        max_rows: int = 500,
        allowed_columns: dict[str, list[str]] | None = None,
    ) -> None:
        """Initialize the SQL connector.

        Args:
            db: ``DatabaseProviderProtocol`` instance.
            allowed_tables: Explicit list of tables that may be queried.
            read_only: Restrict to SELECT statements only (default True).
            max_rows: Maximum rows to return per query (default 500).
            allowed_columns: Static per-table column allowlists. When a table
                has an entry it is authoritative; otherwise columns are
                introspected once from ``information_schema.columns``.

        Raises:
            ValueError: If ``allowed_tables`` is empty.
        """
        if not allowed_tables:
            raise ValueError("SQLConnector requires at least one allowed_table")
        for name in allowed_tables:
            if not _SAFE_IDENT_RE.match(name):
                raise ValueError(
                    f"Invalid table name '{name}'. "
                    "Must be alphanumeric + undersscores only."
                )
        self._db = db
        self._allowed_tables = list(allowed_tables)
        self._read_only = read_only
        self._max_rows = max_rows
        self._allowed_columns = allowed_columns or {}
        self._column_cache: dict[str, list[str]] = {}

    # ------------------------------------------------------------------
    # MCPToolProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return tool definitions for this connector."""
        return [
            MCPToolDefinition(
                name="sql_query",
                description=(
                    "Execute a SELECT query against an allowed table. "
                    "Filters use allowlisted columns and a closed operator set."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "table": {
                            "type": "string",
                            "description": "Table name (must be in the allowlist)",
                        },
                        "filters": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string"},
                                    "op": {
                                        "type": "string",
                                        "description": (
                                            "One of eq, ne, gt, gte, lt, lte, like, in"
                                        ),
                                    },
                                    "value": {},
                                },
                                "required": ["field", "op", "value"],
                            },
                            "description": (
                                "Structured filters. field must be a real "
                                "column of the table."
                            ),
                            "default": [],
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum rows to return",
                            "default": 50,
                        },
                    },
                    "required": ["table"],
                },
            ).to_dict(),
            MCPToolDefinition(
                name="sql_list_tables",
                description="List all tables available in this connector",
                input_schema={"type": "object", "properties": {}},
            ).to_dict(),
            MCPToolDefinition(
                name="sql_describe_table",
                description="Describe column names and types for a table",
                input_schema={
                    "type": "object",
                    "properties": {
                        "table": {
                            "type": "string",
                            "description": "Table name",
                        }
                    },
                    "required": ["table"],
                },
            ).to_dict(),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Dispatch tool calls to handler methods.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            MCPToolResult with JSON data or error.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        dispatch = {
            "sql_query": self._sql_query,
            "sql_list_tables": self._sql_list_tables,
            "sql_describe_table": self._sql_describe_table,
        }
        handler = dispatch.get(name)
        if handler is None:
            raise MCPToolCallError(message=f"Unknown SQL tool: {name}", tool_name=name)
        return await handler(arguments)

    # ------------------------------------------------------------------
    # MCPResourceProviderProtocol interface
    # ------------------------------------------------------------------

    async def list_resources(self) -> list[dict[str, Any]]:
        """List all allowed tables as MCP resources."""
        return [
            MCPResource(
                uri=f"sql://{table}",
                name=table,
                description=f"Database table: {table}",
                mime_type="application/json",
            ).to_dict()
            for table in self._allowed_tables
        ]

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read the first N rows of a table resource.

        Args:
            uri: ``sql://table_name`` URI.

        Returns:
            MCP resource content dict.
        """
        table = uri.removeprefix("sql://")
        result = await self._sql_query({"table": table, "limit": 50})
        text = result.content[0]["text"] if result.content else "[]"
        return {
            "contents": [{"uri": uri, "mimeType": "application/json", "text": text}]
        }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _sql_query(self, arguments: dict[str, Any]) -> MCPToolResult:
        table = arguments.get("table", "")
        filters = arguments.get("filters") or []
        limit = min(int(arguments.get("limit") or 50), self._max_rows)

        if not self._is_allowed_table(table):
            return MCPToolResult.error("Table is not available")

        try:
            columns = await self._columns_for(table)
        except Exception as exc:  # noqa: BLE001 — any DB driver failure is a tool error result
            logger.error("sql_query_load_columns_error", error_type=type(exc).__name__)
            return MCPToolResult.error(f"Failed to load columns ({type(exc).__name__})")

        where_sql, where_params, allowed = self._apply_filters(table, filters, columns)
        if not allowed:
            return MCPToolResult.error(
                "filters reference a field or operator that is not allowed"
            )

        params = list(where_params)
        sql = f"SELECT * FROM {_quote_identifier(table)}"  # noqa: S608 -- table allowlisted + quoted via _quote_identifier
        if where_sql:
            sql += f" WHERE {where_sql}"
        sql += f" LIMIT ${len(params) + 1}"
        params.append(limit)

        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                rows = await conn.fetch(sql, *params)
            data = [dict(row) for row in rows]
            return MCPToolResult.text(dumps_str(data))
        except Exception as exc:  # noqa: BLE001 — any DB driver failure is a tool error result
            logger.error("sql_query_error", error_type=type(exc).__name__)
            return MCPToolResult.error(f"Query failed ({type(exc).__name__})")

    async def _sql_list_tables(self, _arguments: dict[str, Any]) -> MCPToolResult:
        return MCPToolResult.text(dumps_str(self._allowed_tables))

    async def _sql_describe_table(self, arguments: dict[str, Any]) -> MCPToolResult:
        table = arguments.get("table", "")
        if not self._is_allowed_table(table):
            return MCPToolResult.error("Table is not available")
        safe_table = _quote_identifier(table)
        sql = (
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_name = $1 ORDER BY ordinal_position"
        )
        try:
            async with self._db.scoped_context():
                conn = await self._db.get_scoped_connection()
                rows = await conn.fetch(sql, table)
            columns = [
                {"column": r["column_name"], "type": r["data_type"]} for r in rows
            ]
            return MCPToolResult.text(dumps_str(columns))
        except Exception as exc:  # noqa: BLE001 — any DB driver failure is a tool error result
            # Fallback: use a LIMIT 0 SELECT to get column info
            try:
                async with self._db.scoped_context():
                    conn = await self._db.get_scoped_connection()
                    rows = await conn.fetch(f"SELECT * FROM {safe_table} LIMIT 0")  # noqa: S608 -- table allowlisted + quoted via _quote_identifier
                columns = list(rows[0].keys()) if rows else []
                return MCPToolResult.text(dumps_str(columns))
            except Exception as inner_exc:  # noqa: BLE001 — any DB driver failure is a tool error result
                logger.error("sql_describe_error", error_type=type(inner_exc).__name__)
                return MCPToolResult.error(
                    f"Describe failed ({type(inner_exc).__name__})"
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_allowed_table(self, table: str) -> bool:
        return table in self._allowed_tables

    async def _columns_for(self, table: str) -> list[str]:
        """Return the allowlisted columns for a table, static first.

        Args:
            table: The table name.

        Returns:
            The column allowlist (static config or introspected + cached).
        """
        static = self._allowed_columns.get(table)
        if static is not None:
            return static
        if table in self._column_cache:
            return self._column_cache[table]
        sql = (
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = $1 ORDER BY ordinal_position"
        )
        async with self._db.scoped_context():
            conn = await self._db.get_scoped_connection()
            rows = await conn.fetch(sql, table)
        columns = [r["column_name"] for r in rows]
        self._column_cache[table] = columns
        return columns

    def _apply_filters(
        self,
        table: str,
        filters: list[dict[str, Any]],
        columns: list[str],
    ) -> tuple[str, list[Any], bool]:
        """Build a WHERE clause from allowlisted filters.

        Args:
            table: The target table.
            filters: Structured filter objects.
            columns: The allowlisted columns for the table.

        Returns:
            ``(where_sql, params, allowed)`` — ``allowed=False`` rejects
            the filters without executing anything.
        """
        parts: list[str] = []
        params: list[Any] = []
        for flt in filters:
            field = str(flt.get("field", ""))
            op = str(flt.get("op", ""))
            if field not in columns or op not in _FILTER_OPS:
                return "", [], False
            if op == "in":
                values = list(flt.get("value") or [])
                if not values:
                    return "", [], False
                placeholders = ", ".join(
                    f"${len(params) + i + 1}" for i in range(len(values))
                )
                parts.append(f"{Column(field)} IN ({placeholders})")
                params.extend(values)
            else:
                params.append(flt.get("value"))
                parts.append(f"{Column(field)} {_FILTER_OPS[op]} ${len(params)}")
        return " AND ".join(parts), params, True


def _quote_identifier(name: str) -> str:
    """Quote a SQL identifier using ANSI double-quotes."""
    return '"' + name.replace('"', '""') + '"'


__all__ = ["SQLConnector"]
