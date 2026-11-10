"""SQLConnector structured-filter safety tests (F1)."""

from __future__ import annotations

from typing import Any, Self

import pytest

from quadkit.ai.mcp.connectors import sql as sql_module
from quadkit.ai.mcp.connectors.sql import SQLConnector
from quadkit.ai.mcp.types import MCPToolResult


class _FakeConnection:
    """Mirror DatabaseProviderProtocol fetch surface."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[Any]]] = []

    async def fetch(self, sql, *params) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
        """Record the call and return no rows."""
        self.calls.append((sql, list(params)))
        return []


class _FakeDB:
    """Minimal DatabaseProviderProtocol fake for SQLConnector."""

    def __init__(self) -> None:
        self.conn = _FakeConnection()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def scoped_context(self) -> _FakeDB:
        return self

    async def get_scoped_connection(self) -> _FakeConnection:
        return self.conn


def _connector(db: _FakeDB, **kwargs: Any) -> SQLConnector:
    return SQLConnector(
        db=db,
        allowed_tables=["orders"],
        **kwargs,
    )


@pytest.mark.asyncio
async def test_injection_payload_is_inert() -> None:
    """A free-text where payload is ignored; only filters are honored."""
    db = _FakeDB()
    connector = _connector(db, allowed_columns={"orders": ["id"]})

    result = await connector._sql_query(
        {
            "table": "orders",
            "where": "1=0 UNION SELECT password_hash FROM admin_users",
            "params": [],
            "limit": 10,
        }
    )

    assert isinstance(result, MCPToolResult)
    assert not result.is_error
    assert db.conn.calls == [('SELECT * FROM "orders" LIMIT $1', [10])]


@pytest.mark.asyncio
async def test_unknown_field_rejected() -> None:
    """Filters referencing a non-allowlisted column are rejected."""
    db = _FakeDB()
    connector = _connector(db, allowed_columns={"orders": ["id"]})

    result = await connector._sql_query(
        {
            "table": "orders",
            "filters": [{"field": "password_hash", "op": "eq", "value": "x"}],
        }
    )

    assert result.is_error
    assert db.conn.calls == []


@pytest.mark.asyncio
async def test_unknown_operator_rejected() -> None:
    """Filters with an unknown operator are rejected without executing."""
    db = _FakeDB()
    connector = _connector(db, allowed_columns={"orders": ["id"]})

    result = await connector._sql_query(
        {"table": "orders", "filters": [{"field": "id", "op": "DROP", "value": "x"}]}
    )

    assert result.is_error
    assert db.conn.calls == []


@pytest.mark.asyncio
async def test_valid_filters_build_and_parameterize() -> None:
    """Allowlisted filters render quoted columns and $N parameters."""
    db = _FakeDB()
    connector = _connector(db, allowed_columns={"orders": ["id", "status"]})

    result = await connector._sql_query(
        {
            "table": "orders",
            "filters": [
                {"field": "status", "op": "eq", "value": "active"},
                {"field": "id", "op": "in", "value": [1, 2]},
            ],
            "limit": 10,
        }
    )

    assert not result.is_error
    assert len(db.conn.calls) == 1
    sql, params = db.conn.calls[0]
    assert '"status" = $1 AND "id" IN ($2, $3)' in sql
    assert params == ["active", 1, 2, 10]


@pytest.mark.asyncio
async def test_schema_has_no_where_param() -> None:
    """The sql_query tool schema no longer exposes a free-text where."""
    connector = _connector(_FakeDB())
    tools = await connector.list_tools()
    sql_query = next(t for t in tools if t["name"] == "sql_query")
    assert "where" not in sql_query["inputSchema"]["properties"]
    assert "params" not in sql_query["inputSchema"]["properties"]
    assert "callback" not in sql_query["inputSchema"]["properties"]
    assert "filters" in sql_query["inputSchema"]["properties"]


def test_has_dangerous_sql_deleted() -> None:
    """The keyword deny-list helper is removed."""
    assert not hasattr(sql_module, "_has_dangerous_sql")
