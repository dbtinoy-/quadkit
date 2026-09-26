"""Database maintenance utilities for Quadkit Framework"""

from __future__ import annotations

import re
from typing import Any

from quadkit.contracts import ConnectionPoolProtocol
from quadkit.contracts.data.identifiers import Table
from quadkit.logging import get_logger

logger = get_logger(__name__)


def _validate_table_name(table_name: str) -> None:
    """Validate table name matches strict SQL identifier pattern.

    Table names used in f-string interpolation must be explicitly validated
    before use, even though they may come from a Table() object that already
    validates them. This ensures no SQL injection through identifier position.

    Args:
        table_name: The table name to validate.

    Raises:
        ValueError: If the table name doesn't match [a-zA-Z_][a-zA-Z0-9_]*
    """
    pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    if not pattern.match(table_name):
        msg = (
            f"Invalid table name: {table_name!r}. "
            "Table names must match pattern [a-zA-Z_][a-zA-Z0-9_]*"
        )
        raise ValueError(msg)


class DatabaseMaintenance:
    """Database maintenance utilities"""

    def __init__(self, connection_pool: ConnectionPoolProtocol):
        self.connection_pool = connection_pool

    async def vacuum(self, table_name: str | None = None) -> None:
        """Reclaim storage and update statistics"""
        async with self.connection_pool.get_connection() as conn:
            if table_name:
                _validate_table_name(table_name)
                safe_table = Table(table_name)  # validates identifier
                await conn.execute(f"VACUUM {safe_table}")
            else:
                await conn.execute("VACUUM")

    async def analyze(self, table_name: str | None = None) -> None:
        """Update table statistics for query optimization"""
        async with self.connection_pool.get_connection() as conn:
            if table_name:
                _validate_table_name(table_name)
                safe_table = Table(table_name)  # validates identifier
                await conn.execute(f"ANALYZE TABLE {safe_table}")
            else:
                await conn.execute("ANALYZE TABLE")

    async def get_table_sizes(self) -> dict[str, dict[str, Any]]:
        """Get size information for all tables"""
        async with self.connection_pool.get_connection() as conn:
            query = """
            SELECT
                table_name,
                data_length,
                index_length,
                data_length + index_length as total_size
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            ORDER BY total_size DESC
            """
            results = await conn.fetch_all(query)

            sizes = {}
            for row in results:
                sizes[row["table_name"]] = {
                    "data_size": row["data_length"],
                    "index_size": row["index_length"],
                    "total_size": row["total_size"],
                }

            return sizes

    async def get_database_stats(self) -> dict[str, Any]:
        """Get comprehensive database statistics"""
        async with self.connection_pool.get_connection() as conn:
            # Table count
            table_query = "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = DATABASE()"
            table_result = await conn.fetch_one(table_query)

            # Total records
            record_query = """
            SELECT SUM(table_rows) as total_records
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            """
            record_result = await conn.fetch_one(record_query)

            # Database size
            size_query = """
            SELECT
                SUM(data_length + index_length) as total_size,
                SUM(data_length) as data_size,
                SUM(index_length) as index_size
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
            """
            size_result = await conn.fetch_one(size_query)

            return {
                "table_count": table_result["count"] if table_result else 0,
                "total_records": record_result["total_records"] if record_result else 0,
                "database_size": {
                    "total": size_result["total_size"] if size_result else 0,
                    "data": size_result["data_size"] if size_result else 0,
                    "index": size_result["index_size"] if size_result else 0,
                },
            }
