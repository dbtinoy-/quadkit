"""SQL data contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.data.sql.append_log import (
        AppendLogProtocol,
        AppendLogSnapshotStore,
    )
    from quadkit.contracts.data.sql.database import (
        ConnectionPoolProtocol,
        ConnectionProtocol,
        CrudOperationsProtocol,
        DatabaseMetricsProtocol,
        DatabaseProviderProtocol,
        DeleteResult,
        HealthMonitorProtocol,
        InsertResult,
        IsolationLevel,
        MigrationManagerProtocol,
        MigrationRecord,
        QueryResult,
        SchemaManagerProtocol,
        TransactionManagerProtocol,
        UpdateResult,
    )
    from quadkit.contracts.data.sql.mapper import (
        DataMapperProtocol,
        ReadOnlyMapperProtocol,
    )
    from quadkit.contracts.data.sql.migrations import (
        MigrationRunnerProtocol,
        SchemaInitializableProtocol,
    )
    from quadkit.contracts.data.sql.query_log import QueryLogEntry, QueryLoggerProtocol
    from quadkit.contracts.data.sql.sql import InvalidIdentifierError, RawSQL
    from quadkit.contracts.data.sql.sql_dialect import (
        DEFAULT_MAX_IDENTIFIER_LENGTH,
        MAX_IDENTIFIER_LENGTHS,
        SQLDialect,
    )
    from quadkit.contracts.data.sql.unit_of_work import UnitOfWorkProtocol

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "DEFAULT_MAX_IDENTIFIER_LENGTH": (
        "quadkit.contracts.data.sql.sql_dialect",
        "DEFAULT_MAX_IDENTIFIER_LENGTH",
    ),
    "MAX_IDENTIFIER_LENGTHS": (
        "quadkit.contracts.data.sql.sql_dialect",
        "MAX_IDENTIFIER_LENGTHS",
    ),
    "AppendLogProtocol": (
        "quadkit.contracts.data.sql.append_log",
        "AppendLogProtocol",
    ),
    "AppendLogSnapshotStore": (
        "quadkit.contracts.data.sql.append_log",
        "AppendLogSnapshotStore",
    ),
    "ConnectionPoolProtocol": (
        "quadkit.contracts.data.sql.database",
        "ConnectionPoolProtocol",
    ),
    "ConnectionProtocol": (
        "quadkit.contracts.data.sql.database",
        "ConnectionProtocol",
    ),
    "CrudOperationsProtocol": (
        "quadkit.contracts.data.sql.database",
        "CrudOperationsProtocol",
    ),
    "DataMapperProtocol": (
        "quadkit.contracts.data.sql.mapper",
        "DataMapperProtocol",
    ),
    "DatabaseMetricsProtocol": (
        "quadkit.contracts.data.sql.database",
        "DatabaseMetricsProtocol",
    ),
    "DatabaseProviderProtocol": (
        "quadkit.contracts.data.sql.database",
        "DatabaseProviderProtocol",
    ),
    "DeleteResult": (
        "quadkit.contracts.data.sql.database",
        "DeleteResult",
    ),
    "HealthMonitorProtocol": (
        "quadkit.contracts.data.sql.database",
        "HealthMonitorProtocol",
    ),
    "InsertResult": (
        "quadkit.contracts.data.sql.database",
        "InsertResult",
    ),
    "InvalidIdentifierError": (
        "quadkit.contracts.data.sql.sql",
        "InvalidIdentifierError",
    ),
    "IsolationLevel": (
        "quadkit.contracts.data.sql.database",
        "IsolationLevel",
    ),
    "MigrationManagerProtocol": (
        "quadkit.contracts.data.sql.database",
        "MigrationManagerProtocol",
    ),
    "MigrationRecord": (
        "quadkit.contracts.data.sql.database",
        "MigrationRecord",
    ),
    "MigrationRunnerProtocol": (
        "quadkit.contracts.data.sql.migrations",
        "MigrationRunnerProtocol",
    ),
    "SchemaInitializableProtocol": (
        "quadkit.contracts.data.sql.migrations",
        "SchemaInitializableProtocol",
    ),
    "QueryLogEntry": (
        "quadkit.contracts.data.sql.query_log",
        "QueryLogEntry",
    ),
    "QueryLoggerProtocol": (
        "quadkit.contracts.data.sql.query_log",
        "QueryLoggerProtocol",
    ),
    "QueryResult": (
        "quadkit.contracts.data.sql.database",
        "QueryResult",
    ),
    "RawSQL": (
        "quadkit.contracts.data.sql.sql",
        "RawSQL",
    ),
    "ReadOnlyMapperProtocol": (
        "quadkit.contracts.data.sql.mapper",
        "ReadOnlyMapperProtocol",
    ),
    "SQLDialect": (
        "quadkit.contracts.data.sql.sql_dialect",
        "SQLDialect",
    ),
    "SchemaManagerProtocol": (
        "quadkit.contracts.data.sql.database",
        "SchemaManagerProtocol",
    ),
    "TransactionManagerProtocol": (
        "quadkit.contracts.data.sql.database",
        "TransactionManagerProtocol",
    ),
    "UnitOfWorkProtocol": (
        "quadkit.contracts.data.sql.unit_of_work",
        "UnitOfWorkProtocol",
    ),
    "UpdateResult": (
        "quadkit.contracts.data.sql.database",
        "UpdateResult",
    ),
}


def __getattr__(name: str) -> Any:
    """Lazy-load symbols on first access."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Enumerate available attributes for IDE support."""
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "DEFAULT_MAX_IDENTIFIER_LENGTH",
    "MAX_IDENTIFIER_LENGTHS",
    "AppendLogProtocol",
    "AppendLogSnapshotStore",
    "ConnectionPoolProtocol",
    "ConnectionProtocol",
    "CrudOperationsProtocol",
    "DataMapperProtocol",
    "DatabaseMetricsProtocol",
    "DatabaseProviderProtocol",
    "DeleteResult",
    "HealthMonitorProtocol",
    "InsertResult",
    "InvalidIdentifierError",
    "IsolationLevel",
    "MigrationManagerProtocol",
    "MigrationRecord",
    "MigrationRunnerProtocol",
    "QueryLogEntry",
    "QueryLoggerProtocol",
    "QueryResult",
    "RawSQL",
    "ReadOnlyMapperProtocol",
    "SQLDialect",
    "SchemaInitializableProtocol",
    "SchemaManagerProtocol",
    "TransactionManagerProtocol",
    "UnitOfWorkProtocol",
    "UpdateResult",
]
