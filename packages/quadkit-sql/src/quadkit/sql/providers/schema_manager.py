"""
Schema management for database providers.

Handles database schema operations like table creation, dropping, and metadata retrieval.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.identifiers import Column, Table
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.data.sql.database import CrudOperationsProtocol

logger = get_logger(__name__)


class SchemaManager:
    """
    Manages database schema operations.

    This class handles table creation, dropping, existence checks,
    and metadata retrieval operations.
    """

    def __init__(self, crud_operations: CrudOperationsProtocol) -> None:
        self.crud_operations = crud_operations

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        # Prefer provider-level `execute_query` when available so instance-level
        # monkeypatches (tests) work correctly. Fall back to CrudOperations.execute_query.
        executor = getattr(self.crud_operations, "provider", self.crud_operations)

        try:
            result = await executor.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                [table_name],
            )
        except Exception:  # noqa: BLE001 — primary probe failed for any reason; attempt the fallback
            # Fallback for other databases - log and attempt simple probe
            with contextlib.suppress(ImportError, AttributeError, RuntimeError):
                logger.exception("table_exists primary check failed")

            try:
                safe_name = Table(table_name)
                await executor.execute_query(
                    f"SELECT 1 FROM {safe_name} LIMIT 1",  # noqa: S608 -- safe_name is a Table() validated identifier
                )
            except Exception:  # noqa: BLE001 — fallback probe failed; treat the table as absent
                with contextlib.suppress(ImportError, AttributeError, RuntimeError):
                    logger.exception("table_exists fallback probe failed")
                return False
            else:
                return True
        else:
            return len(result.rows) > 0

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for a table"""
        # This is a basic implementation - real implementations should be database-specific
        safe_name = Table(table_name)
        result = await self.crud_operations.execute_query(
            f"PRAGMA table_info({safe_name})",
        )
        return [
            {
                "name": row["name"],
                "type": row["type"],
                "nullable": not row["notnull"],
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in result.rows
        ]

    async def create_table(self, table_name: str, columns: dict[str, str]) -> None:
        """Create a table with given columns"""
        column_defs = []
        is_postgres = getattr(self, "database_type", "sqlite") in [
            "postgresql",
            "postgres",
        ]

        # Validate table and column identifiers
        safe_table = Table(table_name)
        for name, col_type in columns.items():
            safe_col = Column(name)
            if name.lower().endswith("_id"):
                if is_postgres:
                    # Postgres serial type handles primary key and autoincrement
                    column_defs.append(f"{safe_col} SERIAL PRIMARY KEY")
                else:
                    column_defs.append(f"{safe_col} INTEGER PRIMARY KEY AUTOINCREMENT")
            else:
                column_defs.append(f"{safe_col} {col_type}")

        sql = f"CREATE TABLE {safe_table} ({', '.join(column_defs)})"
        executor = getattr(self.crud_operations, "provider", self.crud_operations)
        await executor.execute_query(sql)

    async def drop_table(self, table_name: str) -> None:
        """Drop a table"""
        safe_table = Table(table_name)
        sql = f"DROP TABLE IF EXISTS {safe_table}"
        executor = getattr(self.crud_operations, "provider", self.crud_operations)
        await executor.execute_query(sql)
