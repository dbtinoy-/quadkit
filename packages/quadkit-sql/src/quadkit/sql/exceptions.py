"""Database exceptions — consolidated, extended, and granular.

Provides a semantic exception hierarchy that enables *specific* catch
blocks, eliminating the need for blind ``except Exception`` (BLE001).

Hierarchy
---------
::

    QuadkitError (from quadkit.exceptions)
    └── DatabaseError
        ├── DatabaseConnectionError
        │   ├── ConnectionRefusedError
        │   ├── ConnectionTimeoutError
        │   └── ConnectionPoolError (was ConnectionPoolExhaustedError)
        ├── QueryError
        │   ├── QuerySyntaxError
        │   └── ParameterBindingError
        ├── IntegrityError
        │   ├── DuplicateKeyError
        │   ├── ForeignKeyError
        │   ├── NotNullViolationError
        │   └── CheckConstraintError
        ├── TransactionError
        │   ├── DeadlockError
        │   ├── SerializationError
        │   └── TransactionRollbackError
        ├── SchemaError
        │   ├── TableNotFoundError
        │   ├── ColumnNotFoundError
        │   └── MigrationError (from quadkit.exceptions)
        ├── LockError
        ├── DatabaseTimeoutError
        ├── RepositoryError
        ├── UnitOfWorkError
        └── DriverError
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import (
    DatabaseError,
    MigrationError,
    NotFoundError,
)
from quadkit.contracts.exceptions.base import QuadkitError

# ── Connection errors ──────────────────────────────────────────────


class DatabaseConnectionError(DatabaseError):
    """Base for all connection-related failures.

    Attributes:
        host: The database host that was targeted.
        port: The database port that was targeted.
    """

    _code: str = "QK_ERR_SQL_001"

    def __init__(
        self,
        message: str,
        *,
        host: str | None = None,
        port: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.host = host
        self.port = port


class ConnectionRefusedError(DatabaseConnectionError):
    """Server actively refused the connection."""

    _code: str = "QK_ERR_SQL_002"


class ConnectionTimeoutError(DatabaseConnectionError):
    """Connection attempt timed out."""

    _code: str = "QK_ERR_SQL_003"


class ConnectionPoolError(DatabaseConnectionError):
    """Connection pool exhausted — no connections available within timeout."""

    _code: str = "QK_ERR_SQL_004"


# ── Query errors ───────────────────────────────────────────────────


class QueryError(DatabaseError):
    """Base for query execution failures.

    Attributes:
        sql: The SQL query that failed.
        params: The parameters that were bound.
    """

    _code: str = "QK_ERR_SQL_005"

    def __init__(
        self,
        message: str,
        *,
        sql: str | None = None,
        params: Any | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.sql = sql
        self.params = params


class QuerySyntaxError(QueryError):
    """The SQL query has a syntax error."""

    _code: str = "QK_ERR_SQL_006"


class ParameterBindingError(QueryError):
    """Failed to bind parameters to a query."""

    _code: str = "QK_ERR_SQL_007"


# ── Integrity errors ──────────────────────────────────────────────


class IntegrityError(DatabaseError):
    """Base for constraint violation errors.

    Attributes:
        constraint: The constraint name that was violated.
        table: The table where the violation occurred.
    """

    _code: str = "QK_ERR_SQL_008"

    def __init__(
        self,
        message: str,
        *,
        constraint: str | None = None,
        table: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.constraint = constraint
        self.table = table


class DuplicateKeyError(IntegrityError):
    """Unique constraint or primary key violated."""

    _code: str = "QK_ERR_SQL_009"


class ForeignKeyError(IntegrityError):
    """Foreign key constraint violated."""

    _code: str = "QK_ERR_SQL_010"


class NotNullViolationError(IntegrityError):
    """NOT NULL constraint violated.

    Attributes:
        column: The column that triggered the violation.
    """

    _code: str = "QK_ERR_SQL_011"

    def __init__(
        self,
        message: str,
        *,
        column: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.column = column


class CheckConstraintError(IntegrityError):
    """CHECK constraint violated."""

    _code: str = "QK_ERR_SQL_012"


# ── Transaction errors ─────────────────────────────────────────────


class TransactionError(DatabaseError):
    """Base for transaction-related failures."""

    _code: str = "QK_ERR_SQL_013"


class SerializationError(TransactionError):
    """Serialization failure (optimistic concurrency conflict)."""

    _code: str = "QK_ERR_SQL_014"


class OptimisticLockError(DatabaseError):
    """Raised when an optimistic lock check fails on UPDATE.

    Indicates a concurrent modification was detected: the row's version
    column did not match the expected value, so the UPDATE affected 0 rows.

    Args:
        entity_type: Class name of the entity that failed the version check.
        entity_id: Primary key of the entity.
        expected_version: The version the caller expected to update from.
    """

    _code: str = "QK_ERR_SQL_015"

    def __init__(
        self,
        entity_type: str,
        entity_id: str | int,
        expected_version: int,
    ) -> None:
        super().__init__(
            f"Optimistic lock conflict on {entity_type}(id={entity_id}): "
            f"expected version {expected_version} but row was modified concurrently."
        )
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.expected_version = expected_version


class TransactionRollbackError(TransactionError):
    """Transaction was rolled back (not by the application)."""

    _code: str = "QK_ERR_SQL_016"


# ── Lock errors ────────────────────────────────────────────────────


class LockError(DatabaseError):
    """Raised when a database lock cannot be acquired."""

    _code: str = "QK_ERR_SQL_017"


class DeadlockError(TransactionError):
    """Database deadlock detected.

    Inherits from :class:`TransactionError` because deadlocks are
    resolved by rolling back one of the transactions.
    """

    _code: str = "QK_ERR_SQL_018"


# ── Schema errors ──────────────────────────────────────────────────


class SchemaError(DatabaseError):
    """Base for schema-related errors."""

    _code: str = "QK_ERR_SQL_019"


class TableNotFoundError(SchemaError):
    """Referenced table does not exist."""

    _code: str = "QK_ERR_SQL_020"


class ColumnNotFoundError(SchemaError):
    """Referenced column does not exist."""

    _code: str = "QK_ERR_SQL_021"


# Note: MigrationError is imported from quadkit.exceptions and
# re-exported for convenience.  It implicitly relates to SchemaError
# but keeps its existing base class for backward compatibility.


# ── Timeout ────────────────────────────────────────────────────


class DatabaseTimeoutError(DatabaseError):
    """Database operation timed out."""

    _code: str = "QK_ERR_SQL_022"


# ── RepositoryProtocol ─────────────────────────────────────────────────


class RepositoryError(DatabaseError):
    """RepositoryProtocol-level operation failure."""

    _code: str = "QK_ERR_SQL_023"


# ── Unit of Work ───────────────────────────────────────────────


class UnitOfWorkError(DatabaseError):
    """Raised when unit of work operation fails."""

    _code: str = "QK_ERR_SQL_024"


# ── Driver wrapper ─────────────────────────────────────────────


class DriverError(DatabaseError):
    """Wraps underlying database driver exceptions.

    Preserves the original exception as ``__cause__`` and adds context
    about the operation being performed.

    Attributes:
        driver: The driver name (e.g. ``"asyncpg"``, ``"aiosqlite"``).
        operation: The operation being performed (e.g. ``"query"``, ``"connect"``).
    """

    _code: str = "QK_ERR_SQL_025"

    def __init__(
        self,
        message: str,
        *,
        driver: str | None = None,
        operation: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.driver = driver
        self.operation = operation


# ── Abstract data-layer exceptions ───────────────────────────────────────────
#
# These are distinct from the SQL-specific exceptions above. They model
# failures in the abstract data access layer and do not require a SQL backend.


class DataError(QuadkitError):
    """Base exception for data access layer failures."""

    _code: str = "QK_ERR_SQL_026"


class DataQueryError(DataError):
    """Raised when a query cannot be built or compiled.

    Args:
        message: Explanation of the query error.
    """

    _code: str = "QK_ERR_SQL_027"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PaginationError(DataError):
    """Raised when pagination parameters are invalid.

    Args:
        message: Explanation of the pagination error.
    """

    _code: str = "QK_ERR_SQL_028"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class EntityNotFoundError(DataError):
    """Signals that a required entity does not exist.

    RepositoryProtocol implementations that cannot find the requested record
    **raise** this exception as a low-level error.  Service-layer callers
    that want to surface the absence as a typed, handleable failure should
    catch the exception and return it wrapped in ``Err``.

    Args:
        entity_type: Name of the entity type that was not found.
        entity_id: Identifier that was looked up.
    """

    _code: str = "QK_ERR_SQL_029"

    def __init__(self, entity_type: str, entity_id: object) -> None:
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id={entity_id!r} not found")


class DataRepositoryError(DataError):
    """Raised when a repository operation fails unexpectedly.

    Args:
        message: Explanation of the repository failure.
    """

    _code: str = "QK_ERR_SQL_030"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class CursorError(DataError):
    """Raised when a cursor cannot be encoded or decoded.

    Args:
        message: Explanation of the cursor error.
    """

    _code: str = "QK_ERR_SQL_031"

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ── Tenant scoping ────────────────────────────────────────────────────


class TenantScopingError(DatabaseError):
    """Raised when a tenant-scoped operation runs without an active tenant.

    Mirrors :class:`~quadkit.sql.row_level_security.NoSecurityPolicyError`:
    a ``multi_tenant`` repository may only run when a tenant is active in
    the db context, or inside an explicit
    :meth:`SQLRepository.with_tenant_scope` block.  Holds the query context
    for operator triage.

    Attributes:
        table: Table that was queried/scoped.
        operation: SQL operation attempted (``SELECT``, ``INSERT``, ...).
    """

    _code: str = "QK_ERR_SQL_038"

    def __init__(self, table: str, operation: str = "SELECT") -> None:
        super().__init__(
            f"Tenant scoping violation: attempted {operation} on table "
            f"'{table}' without an active tenant. Activate a tenant in the "
            f"db context or use repository.with_tenant_scope(tenant_id) "
            f"for an explicit scoped run."
        )
        self.table = table
        self.operation = operation


__all__ = [
    "CheckConstraintError",
    "ColumnNotFoundError",
    "ConnectionPoolError",
    "ConnectionRefusedError",
    "ConnectionTimeoutError",
    "CursorError",
    "DataError",
    "DataQueryError",
    "DataRepositoryError",
    "DatabaseConnectionError",
    "DatabaseError",
    "DatabaseTimeoutError",
    "DeadlockError",
    "DriverError",
    "DuplicateKeyError",
    "EntityNotFoundError",
    "ForeignKeyError",
    "IntegrityError",
    "LockError",
    "MigrationError",
    "NotFoundError",
    "NotNullViolationError",
    "OptimisticLockError",
    "PaginationError",
    "ParameterBindingError",
    "QueryError",
    "QuerySyntaxError",
    "RepositoryError",
    "SchemaError",
    "SerializationError",
    "TableNotFoundError",
    "TenantScopingError",
    "TransactionError",
    "TransactionRollbackError",
    "UnitOfWorkError",
]
