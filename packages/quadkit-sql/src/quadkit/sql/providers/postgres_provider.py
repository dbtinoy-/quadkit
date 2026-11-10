"""
PostgreSQL database provider for community edition
"""

from __future__ import annotations

from typing import Any

from quadkit import serialization as json

asyncpg: Any
try:
    import asyncpg as _asyncpg

    asyncpg = _asyncpg
except ImportError:
    asyncpg = None

from quadkit.contracts.data.identifiers import (
    Column,
    Delta,
    Table,
    validate_identifier,
)
from quadkit.contracts.data.sql.database import encode_bind_value
from quadkit.logging import get_logger
from quadkit.sql import InsertResult
from quadkit.sql.exceptions import (
    CheckConstraintError,
    DatabaseConnectionError,
    DuplicateKeyError,
    ForeignKeyError,
    IntegrityError,
    QueryError,
    TransactionError,
)
from quadkit.sql.providers.base_provider import (
    DatabaseDriver,
)
from quadkit.sql.providers.crud_operations import DatabaseOperationContext

logger = get_logger(__name__)


def _encode_jsonb(value: Any) -> str:
    """Encode Python values or pre-serialized JSON object/array strings for JSONB."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in ("{", "["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, (dict, list)):
                    return stripped
            except ValueError:
                pass
    return json.dumps_str(value)


def _decode_jsonb(raw: str) -> Any:
    """Decode JSONB text, unwrapping legacy double-encoded object/array strings."""
    decoded = json.loads(raw)
    if isinstance(decoded, str):
        stripped = decoded.strip()
        if stripped[:1] in ("{", "["):
            try:
                inner = json.loads(stripped)
                if isinstance(inner, (dict, list)):
                    return inner
            except ValueError:
                pass
    return decoded


class PostgresProvider(DatabaseDriver):
    """
    PostgreSQL database provider implementation

    Uses asyncpg for async PostgreSQL operations.
    """

    name = "postgres"

    def __init__(self, connection_string: str, **kwargs: Any) -> None:
        super().__init__(connection_string, **kwargs)
        self._array_columns_cache: dict[str, frozenset[str]] = {}

    async def _get_array_columns(self, table_name: str) -> frozenset[str]:
        """Return cached set of PostgreSQL ``ARRAY`` column names for *table_name*."""
        cached = self._array_columns_cache.get(table_name)
        if cached is not None:
            return cached
        try:
            result = await self.execute_query(
                "SELECT column_name AS name FROM information_schema.columns "
                "WHERE table_schema = ANY(current_schemas(false)) "
                "AND table_name = $1 AND data_type = 'ARRAY'",
                [table_name],
            )
            cols = frozenset(str(row["name"]) for row in result.rows if "name" in row)
        except Exception:  # noqa: BLE001 — fall back cleanly on mocked connections
            cols = frozenset()
        self._array_columns_cache[table_name] = cols
        return cols

    async def _encode_column_value(
        self,
        table: str,
        column_name: str,
        value: Any,
        array_cols: frozenset[str],
    ) -> Any:
        """Bind native Python lists for PostgreSQL ``ARRAY`` columns; JSON-encode others."""
        if isinstance(value, list) and column_name in array_cols:
            return list(value)
        return encode_bind_value(value)

    async def _create_connection(self) -> Any:
        """Create PostgreSQL connection"""
        # Parse connection string for asyncpg
        conn_kwargs = {
            "host": self.connection_manager.host,
            "port": self.connection_manager.port,
            "user": self.connection_manager.username,
            "password": self.connection_manager.password,
            "database": self.connection_manager.database,
        }

        # Filter out None values
        conn_kwargs = {k: v for k, v in conn_kwargs.items() if v is not None}

        try:
            conn = await asyncpg.connect(**conn_kwargs)
        except asyncpg.InvalidCatalogNameError:
            # Database doesn't exist, try to create it
            target_db = conn_kwargs.get("database")
            if not isinstance(target_db, str):
                raise ConnectionError(
                    "Cannot auto-create database: 'database' connect kwarg "
                    f"is missing or not a string (got {target_db!r})"
                ) from None
            logger.info(
                "Database '%s' does not exist. Attempting to create it...", target_db
            )

            # Connect to default 'postgres' database to run CREATE DATABASE
            admin_kwargs = conn_kwargs.copy()
            admin_kwargs["database"] = "postgres"

            try:
                admin_conn = await asyncpg.connect(**admin_kwargs)
                try:
                    # CREATE DATABASE cannot run in a transaction block
                    await admin_conn.execute(
                        f'CREATE DATABASE "{validate_identifier(target_db)}"'
                    )
                    logger.info("Successfully created database '%s'", target_db)
                finally:
                    await admin_conn.close()

                # Retry connection to the newly created database
                conn = await asyncpg.connect(**conn_kwargs)
            except Exception as create_err:  # noqa: BLE001 — any auto-creation failure becomes the documented ConnectionError
                logger.error(
                    "Failed to auto-create database '%s': %s", target_db, create_err
                )
                raise ConnectionError(
                    f"Database '{target_db}' does not exist and auto-creation failed"
                ) from create_err

        # Register JSONB codec - the encoder MUST return str (not bytes)
        # because asyncpg format='text' (the default) expects str.
        await conn.set_type_codec(
            "jsonb",
            encoder=_encode_jsonb,
            decoder=_decode_jsonb,
            schema="pg_catalog",
        )
        return conn

    async def _close_connection(self, connection: Any) -> None:
        """Close PostgreSQL connection"""
        await connection.close()

    async def _execute_query_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute SELECT query"""
        try:
            if isinstance(params, dict):
                # Named parameters with $param syntax
                rows = await connection.fetch(sql, **params)
            else:
                # Positional parameters with ? converted to $1, $2, etc.
                sql = self._convert_sql(sql)
                rows = await connection.fetch(sql, *(params or []))
            return [dict(row) for row in rows]
        except (
            asyncpg.PostgresError,
            asyncpg.InterfaceError,
            asyncpg.InternalClientError,
        ) as e:
            self._handle_postgres_error(e, sql, params)
            raise

    async def _execute_modify_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | dict[str, Any] | None = None,
    ) -> int:
        """Execute INSERT/UPDATE/DELETE"""
        try:
            if isinstance(params, dict):
                # Named parameters with $param syntax
                result = await connection.execute(sql, **params)
            else:
                # Positional parameters with ? converted to $1, $2, etc.
                sql = self._convert_sql(sql)
                result = await connection.execute(sql, *(params or []))
            # Parse affected rows from result string like "UPDATE 5" or "INSERT 0 1"
            parts = result.split()
            if len(parts) >= 2 and parts[0] in ["UPDATE", "DELETE", "INSERT"]:
                try:
                    return int(parts[-1])
                except ValueError:
                    pass
            return 0
        except (
            asyncpg.PostgresError,
            asyncpg.InterfaceError,
            asyncpg.InternalClientError,
        ) as e:
            self._handle_postgres_error(e, sql, params)
            raise

    def _handle_postgres_error(
        self,
        e: Any,
        sql: str | None = None,
        params: Any = None,
    ) -> None:
        """Translate PostgreSQL exceptions to Quadkit exceptions"""
        msg = str(e)
        if not asyncpg:
            raise e

        if isinstance(e, asyncpg.IntegrityConstraintViolationError):
            if isinstance(e, asyncpg.UniqueViolationError):
                raise DuplicateKeyError(msg, cause=e) from e
            if isinstance(e, asyncpg.ForeignKeyViolationError):
                raise ForeignKeyError(msg, cause=e) from e
            if isinstance(e, asyncpg.CheckViolationError):
                raise CheckConstraintError(msg, cause=e) from e
            raise IntegrityError(msg, cause=e) from e

        if isinstance(e, (asyncpg.InterfaceError, asyncpg.InternalClientError)):
            raise DatabaseConnectionError(msg, cause=e) from e

        raise QueryError(msg, sql=sql, params=params, cause=e) from e

    def _convert_sql(self, sql: str) -> str:
        """Convert standard SQL placeholders (?) to PostgreSQL ($n)"""
        if "?" not in sql:
            return sql

        parts = sql.split("?")
        if len(parts) == 1:
            return sql

        res = []
        for i, part in enumerate(parts[:-1]):
            res.append(part)
            res.append(f"${i + 1}")
        res.append(parts[-1])
        return "".join(res)

    def _check_outer_transaction_boundary(self, connection: Any) -> None:
        # A raw asyncpg connection tracks server transaction state. Unknown
        # adapters and wrappers do not gain an ownership guarantee here.
        if (
            asyncpg is not None
            and type(connection) is asyncpg.Connection
            and connection.is_in_transaction()
        ):
            raise TransactionError("connection already has an active transaction")

    async def _begin_transaction_raw(
        self, connection: Any, isolation: Any | None = None
    ) -> None:
        """Begin transaction with optional isolation level."""
        await connection.execute("BEGIN")
        if isolation is not None:
            await connection.execute(
                f"SET TRANSACTION ISOLATION LEVEL {isolation.value}"
            )

    async def _commit_transaction_raw(self, connection: Any) -> None:
        """Commit transaction"""
        await connection.execute("COMMIT")

    async def _rollback_transaction_raw(self, connection: Any) -> None:
        """Rollback transaction"""
        await connection.execute("ROLLBACK")

    async def execute_insert(
        self,
        table: str,
        data: dict[str, Any],
        **_kwargs: Any,
    ) -> InsertResult:
        """Execute an INSERT ... RETURNING * to capture server-generated keys."""
        if not data:
            return await super().execute_insert(table, data, **_kwargs)

        safe_table = Table(table)
        safe_columns = ", ".join(str(Column(c)) for c in data)
        placeholders = ", ".join("?" for _ in data)
        array_cols = (
            await self._get_array_columns(table)
            if any(isinstance(v, list) for v in data.values())
            else frozenset()
        )
        values = [
            await self._encode_column_value(table, col, val, array_cols)
            for col, val in data.items()
        ]
        sql = f"INSERT INTO {safe_table} ({safe_columns}) VALUES ({placeholders}) RETURNING *"  # noqa: S608 -- safe_table/columns are Table()/Column() quoted identifiers, values parameterized

        ctx = DatabaseOperationContext(
            self.connection_manager,
            self.query_executor,
            sql,
            values,
        )
        async with ctx:
            rows = await self.query_executor.execute_query(ctx.conn, sql, values)

        inserted_id: Any = None
        if rows:
            first_row = rows[0]
            if "id" in first_row and first_row["id"] is not None:
                inserted_id = first_row["id"]
            else:
                for col_name, col_val in first_row.items():
                    if (
                        col_val is not None
                        and col_name.endswith("_id")
                        and (col_name not in data or data.get(col_name) is None)
                    ):
                        inserted_id = col_val
                        break
                if inserted_id is None:
                    for col_name, col_val in first_row.items():
                        if col_val is not None and (
                            col_name not in data or data.get(col_name) is None
                        ):
                            inserted_id = col_val
                            break
                if inserted_id is None:
                    inserted_id = next(
                        (v for v in first_row.values() if v is not None),
                        None,
                    )

        return InsertResult(
            inserted_id=inserted_id,
            affected_rows=len(rows) if rows else 1,
            execution_time=ctx.get_execution_time(),
            success=True,
        )

    async def execute_update(
        self,
        table: str,
        data: dict[str, Any],
        where_clause: str,
        where_params: list[Any] | None = None,
        **_kwargs: Any,
    ) -> Any:
        """Execute an UPDATE preserving native lists for PostgreSQL ``ARRAY`` columns."""
        from quadkit.sql import UpdateResult

        safe_table = Table(table)
        array_cols = (
            await self._get_array_columns(table)
            if any(isinstance(v, list) for v in data.values())
            else frozenset()
        )
        assignments: list[str] = []
        values: list[Any] = []
        for key, value in data.items():
            column = Column(key)
            if isinstance(value, Delta):
                assignments.append(f"{column} = {value.to_sql()}")
                values.append(encode_bind_value(value.amount))
            else:
                assignments.append(f"{column} = ?")
                values.append(
                    await self._encode_column_value(table, key, value, array_cols)
                )
        set_clause = ", ".join(assignments)
        sql = f"UPDATE {safe_table} SET {set_clause} WHERE {where_clause}"  # noqa: S608

        if where_params:
            values.extend(where_params)

        ctx = DatabaseOperationContext(
            self.connection_manager,
            self.query_executor,
            sql,
            values,
        )
        async with ctx:
            affected_rows = await self.query_executor.execute_modify(
                ctx.conn,
                sql,
                values,
            )

        return UpdateResult(
            affected_rows=affected_rows,
            execution_time=ctx.get_execution_time(),
            success=True,
        )

    async def _get_last_insert_id(self, connection: Any, _table: str) -> Any | None:
        """Get last inserted ID using RETURNING or currval"""
        return None

    async def table_exists(self, table_name: str) -> bool:
        """Check if table exists in PostgreSQL"""
        result = await self.execute_query(
            "SELECT EXISTS ("
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = ANY(current_schemas(false)) AND table_name = $1"
            ")",
            [table_name],
        )
        return bool(result.rows[0]["exists"]) if result.rows else False

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """Get column information for PostgreSQL table"""
        sql = """
        SELECT
            column_name as name,
            data_type as type,
            is_nullable = 'YES' as nullable,
            column_default as default,
            is_identity = 'YES' as primary_key
        FROM information_schema.columns
        WHERE table_schema = ANY(current_schemas(false)) AND table_name = $1
        ORDER BY ordinal_position
        """
        result = await self.execute_query(sql, [table_name])
        return result.rows
