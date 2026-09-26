"""
SQLite database provider for community edition
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

aiosqlite: Any = None
try:
    import sqlite3

    import aiosqlite as _aiosqlite

    aiosqlite = _aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False
    aiosqlite = None

from quadkit.sql.exceptions import (
    CheckConstraintError,
    DatabaseConnectionError,
    DuplicateKeyError,
    ForeignKeyError,
    IntegrityError,
    QueryError,
)
from quadkit.sql.providers.base_provider import (
    DatabaseDriver,
)


class SQLiteProvider(DatabaseDriver):
    """
    SQLite database provider implementation

    Uses aiosqlite for async SQLite operations.
    """

    name = "sqlite"

    def __init__(self, database_path: str = ":memory:", **kwargs: Any) -> None:
        if not HAS_AIOSQLITE:
            raise ImportError(
                "aiosqlite is required for SQLiteProvider. Install it with: pip install aiosqlite",
            )
        # Accept a raw filesystem path (e.g., '/var/db/test.db') or any
        # sqlite connection string — the sync scheme ('sqlite:///') or any
        # async driver variant ('sqlite+aiosqlite:///', 'sqlite+pysqlite:///',
        # ...). All schemes normalize to a bare path + canonical
        # 'sqlite:///' connection string, because the pool layer connects
        # via aiosqlite directly from the extracted path.
        path: str | None = None
        if isinstance(database_path, str):
            scheme_match = re.match(r"^sqlite(?:\+[a-zA-Z0-9_]+)?:", database_path)
            if scheme_match:
                rest = database_path[scheme_match.end() :]
                if rest.startswith("///"):
                    path = rest[3:]
                elif rest.startswith("//"):
                    path = ""  # authority-only form -> in-memory
                else:
                    path = rest
                path = path or ":memory:"

        if path is not None:
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            connection_string = f"sqlite:///{path}"
            self.database = path.lstrip("/") if path.startswith("/") else path
        elif database_path == ":memory:":
            connection_string = "sqlite:///:memory:"
            self.database = ":memory:"
        else:
            # Treat as a filesystem path
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
            connection_string = f"sqlite:///{database_path}"
            # Normalize stored database identifier (strip leading slash)
            self.database = (
                database_path.lstrip("/")
                if isinstance(database_path, str) and database_path.startswith("/")
                else database_path
            )

        # Expose for tests/consumers (base stores it on the connection manager)
        self.connection_string = connection_string
        super().__init__(connection_string, **kwargs)

    async def _create_connection(self) -> Any:
        """Create SQLite connection"""
        # Extract path from connection string
        path = self.connection_manager.connection_string.replace("sqlite:///", "")
        path = ":memory:" if path == ":memory:" else path or ":memory:"

        conn = await aiosqlite.connect(path)
        # Enable row factory for dict-like access
        conn.row_factory = aiosqlite.Row
        # WAL allows concurrent readers/writers without SQLITE_BUSY; the
        # busy_timeout makes a writer wait instead of failing immediately
        # when another connection holds the write lock momentarily.
        if path != ":memory:":
            await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA busy_timeout=5000")
        return conn

    async def _close_connection(self, connection: Any) -> None:
        """Close SQLite connection"""
        await connection.close()

    async def _execute_query_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute SELECT query"""
        try:
            cursor = await connection.execute(sql, params or [])
            rows = await cursor.fetchall()
            # Capture column names from cursor description when available
            desc = getattr(cursor, "description", None)
            if desc and isinstance(desc, (list, tuple)):
                columns = [col[0] for col in desc]
            else:
                columns = []
            await cursor.close()

            # Convert rows to list[dict]
            if columns:
                return [dict(zip(columns, row, strict=False)) for row in rows]
            # Fallback for non-descriptive rows
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            self._handle_sqlite_error(e, sql, params)
            raise

    async def _execute_modify_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        """Execute INSERT/UPDATE/DELETE"""
        try:
            cursor = await connection.execute(sql, params or [])
            # Only commit immediately if not inside an explicit transaction
            if not self.transaction_manager.in_transaction:
                await connection.commit()
            await cursor.close()
            return cursor.rowcount or 0
        except sqlite3.Error as e:
            self._handle_sqlite_error(e, sql, params)
            raise

    def _handle_sqlite_error(
        self,
        e: sqlite3.Error,
        sql: str | None = None,
        params: Any = None,
    ) -> None:
        """Translate SQLite exceptions to Quadkit exceptions"""
        msg = str(e)
        if isinstance(e, sqlite3.IntegrityError):
            if "UNIQUE constraint failed" in msg:
                raise DuplicateKeyError(msg, cause=e) from e
            if "FOREIGN KEY constraint failed" in msg:
                raise ForeignKeyError(msg, cause=e) from e
            if "CHECK constraint failed" in msg:
                raise CheckConstraintError(msg, cause=e) from e
            raise IntegrityError(msg, cause=e) from e

        if isinstance(e, sqlite3.OperationalError):
            if "unable to open database file" in msg:
                raise DatabaseConnectionError(msg, cause=e) from e

        raise QueryError(msg, sql=sql, params=params, cause=e) from e

    # Maps canonical isolation levels to SQLite locking modes (best-effort).
    _SQLITE_ISOLATION_MAP: dict[str, str] = {
        "READ UNCOMMITTED": "DEFERRED",
        "READ COMMITTED": "DEFERRED",
        "REPEATABLE READ": "IMMEDIATE",
        "SERIALIZABLE": "EXCLUSIVE",
    }

    async def _begin_transaction_raw(
        self, connection: Any, isolation: Any | None = None
    ) -> None:
        """Begin transaction with best-effort isolation level mapping."""
        mode = (
            self._SQLITE_ISOLATION_MAP.get(isolation.value, "DEFERRED")
            if isolation
            else ""
        )
        stmt = f"BEGIN {mode}" if mode else "BEGIN"
        await connection.execute(stmt)

    async def _commit_transaction_raw(self, connection: Any) -> None:
        """Commit transaction"""
        await connection.commit()

    async def _rollback_transaction_raw(self, connection: Any) -> None:
        """Rollback transaction"""
        await connection.rollback()

    async def _get_last_insert_id(self, connection: Any, _table: str) -> Any | None:
        """Get last inserted rowid"""
        cursor = await connection.execute("SELECT last_insert_rowid()")
        result = await cursor.fetchone()
        await cursor.close()
        return result[0] if result else None

    async def table_exists(self, table_name: str) -> bool:
        """Check if table exists in SQLite"""
        result = await self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            [table_name],
        )
        return len(result.rows) > 0

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for SQLite table"""
        result = await self.execute_query(f"PRAGMA table_info({table_name})")
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
