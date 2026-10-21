"""Database provider protocols.

These protocols define the contract for database implementations,
enabling swappable database backends (PostgreSQL, MySQL, SQLite, MongoDB).
"""

from __future__ import annotations

from quadkit.contracts.data.sql.database._binding import (
    encode_bind_value,
    encode_bind_values,
)
from quadkit.contracts.data.sql.database._connection import ConnectionProtocol
from quadkit.contracts.data.sql.database._dialect import provider_dialect
from quadkit.contracts.data.sql.database._managers import (
    CrudOperationsProtocol,
    DatabaseMetricsProtocol,
    HealthMonitorProtocol,
    SchemaManagerProtocol,
    TransactionManagerProtocol,
)
from quadkit.contracts.data.sql.database._migration import (
    MigrationManagerProtocol,
    MigrationRecord,
)
from quadkit.contracts.data.sql.database._pool import ConnectionPoolProtocol
from quadkit.contracts.data.sql.database._provider import DatabaseProviderProtocol
from quadkit.contracts.data.sql.database._results import (
    DeleteResult,
    InsertResult,
    IsolationLevel,
    QueryResult,
    UpdateResult,
)

__all__ = [
    "ConnectionPoolProtocol",
    "ConnectionProtocol",
    "CrudOperationsProtocol",
    "DatabaseMetricsProtocol",
    "DatabaseProviderProtocol",
    "DeleteResult",
    "HealthMonitorProtocol",
    "InsertResult",
    "IsolationLevel",
    "MigrationManagerProtocol",
    "MigrationRecord",
    "QueryResult",
    "SchemaManagerProtocol",
    "TransactionManagerProtocol",
    "UpdateResult",
    "encode_bind_value",
    "encode_bind_values",
    "provider_dialect",
]
