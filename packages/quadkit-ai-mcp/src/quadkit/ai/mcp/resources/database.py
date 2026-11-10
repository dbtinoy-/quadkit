"""Database resource provider — exposes database tables as MCP resources.

Allows MCP clients to browse and read database records without
custom code.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from quadkit.ai.mcp.types import MCPResource
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import dumps_str

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.contracts.data import DatabaseProviderProtocol

# Allowlist pattern: only alphanumeric characters and underscores (no operators,
# quotes, semicolons, or whitespace permitted in table names).
_SAFE_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DatabaseResourceProvider:
    """Exposes database tables as MCP resources.

    Each table becomes a browsable resource. Records can be
    read by their primary key via URI.

    Usage::

        provider = DatabaseResourceProvider(
            db=database_provider,
            tables=["orders", "customers", "products"],
            uri_prefix="db",
        )
        registry.register(provider)

    URIs: ``db://orders``, ``db://orders/ORD-123``
    """

    name = "database"
    description = "Database records"
    mime_type = "application/json"

    def __init__(
        self,
        db: DatabaseProviderProtocol,
        tables: list[str] | None = None,
        uri_prefix: str = "db",
        max_list_items: int = 50,
    ) -> None:
        # Validate all table names at construction time so invalid names are
        # caught early rather than at query time.
        validated: list[str] = []
        for name in tables or []:
            if not _SAFE_TABLE_NAME_RE.match(name):
                raise ValueError(
                    f"Table name {name!r} contains invalid characters. "
                    "Only letters, digits, and underscores are allowed, "
                    "and the name must start with a letter or underscore."
                )
            validated.append(name)
        self._db = db
        self._tables = validated
        self._uri_prefix = uri_prefix
        self._max_list = max_list_items

    @property
    def uri_template(self) -> str:
        return f"{self._uri_prefix}://{{table}}/{{id}}"

    def can_handle(self, uri: str) -> bool:
        """Check if this provider handles the given URI."""
        return uri.startswith(f"{self._uri_prefix}://")

    async def list(self) -> list[MCPResource]:
        """List available database tables as resources."""
        resources = []
        for table in self._tables:
            resources.append(
                MCPResource(
                    uri=f"{self._uri_prefix}://{table}",
                    name=f"Table: {table}",
                    description=f"Records in the {table} table",
                    mime_type="application/json",
                )
            )
        return resources

    async def read(self, uri: str) -> str:
        """Read a database resource.

        - ``db://orders`` → list recent records
        - ``db://orders/ORD-123`` → single record by ID
        """
        parts = uri.replace(f"{self._uri_prefix}://", "").split("/", 1)
        table = parts[0]

        # Enforce allowlist — table must be in the configured set AND pass
        # the safe-name pattern so injection via URI manipulation is blocked.
        if table not in self._tables:
            logger.warning("database_resource_table_not_allowed")
            return dumps_str({"error": "Table is not available"})

        if not _SAFE_TABLE_NAME_RE.match(table):
            logger.warning("database_resource_invalid_table_name")
            return dumps_str({"error": "Invalid table name"})

        # Use double-quote identifier escaping for the table name.  Note that
        # table *names* cannot be passed as query parameters ($1), so manual
        # escaping is required.  The allowlist check above already prevents
        # injection; this escaping is a defence-in-depth measure.
        safe_table = table.replace('"', '""')

        try:
            if len(parts) == 1:
                # List records — use parameterized $1 for the LIMIT value
                async with self._db.scoped_context():
                    conn = await self._db.get_scoped_connection()
                    result = await conn.fetch(
                        f'SELECT * FROM "{safe_table}" LIMIT $1',  # noqa: S608 -- table allowlisted + double-quote-escaped
                        self._max_list,
                    )
                    return dumps_str(result)
            else:
                # Single record — fully parameterized
                record_id = parts[1]
                async with self._db.scoped_context():
                    conn = await self._db.get_scoped_connection()
                    result = await conn.fetch(
                        f'SELECT * FROM "{safe_table}" WHERE id = $1',  # noqa: S608 -- table allowlisted + double-quote-escaped
                        record_id,
                    )
                    if result:
                        return dumps_str(result[0])
                    return dumps_str({"error": "Record not found"})
        except Exception as exc:  # noqa: BLE001 — resource read failures are logged, never raised
            error_type = type(exc).__name__
            logger.error("database_resource_error", error_type=error_type)
            return dumps_str({"error": f"Database resource read failed ({error_type})"})
