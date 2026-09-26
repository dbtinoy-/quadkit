"""Quadkit DB Package — Database integration and repository pattern.

**Preferred import paths (D9.1)**

Use the most specific sub-namespace rather than the root namespace wherever
possible — this keeps import times low and makes dependencies clear:

+------------------------+-----------------------------------------------+
| What you need          | Import from                                   |
+========================+===============================================+
| DI provider            | ``quadkit.sql.di.provider``                   |
+------------------------+-----------------------------------------------+
| Query building         | ``quadkit.sql.query``                         |
+------------------------+-----------------------------------------------+
| SQL dialect builder    | ``quadkit.sql.query``                         |
+------------------------+-----------------------------------------------+
| RepositoryProtocol base        | ``quadkit.sql.repositories``                  |
+------------------------+-----------------------------------------------+
| Schema / ORM models    | ``quadkit.sql.schema`` or ``quadkit.sql.orm`` |
+------------------------+-----------------------------------------------+
| Migration tools        | ``quadkit.sql.migrations``                    |
+------------------------+-----------------------------------------------+
| Unit of Work           | ``quadkit.sql.unit_of_work``                  |
+------------------------+-----------------------------------------------+
| DatabaseService        | ``quadkit.sql.providers``                     |
+------------------------+-----------------------------------------------+
| Contracts              | ``quadkit.contracts.data``                   |
+------------------------+-----------------------------------------------+

The root namespace (``from quadkit.sql import ...``) is retained for
backward compatibility and for the handful of frequently-used types
documented below.  It should **not** grow further.
"""

from __future__ import annotations

import importlib.metadata
import sys
from typing import TYPE_CHECKING, Any

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from quadkit.sql.constants import __version__ as __version__

# Lazy loading to avoid circular imports

if TYPE_CHECKING:
    from quadkit.contracts.audit import AuditEntry
    from quadkit.contracts.core import HealthStatus
    from quadkit.contracts.core.lifecycle import (  # type: ignore[attr-defined]
        HealthCheckResult,
    )
    from quadkit.contracts.data import (
        ConnectionPoolProtocol,
        DatabaseProviderProtocol,
        DeleteResult,
        InsertResult,
        QueryLogEntry,
        QueryLoggerProtocol,
        QueryResult,
        UpdateResult,
    )
    from quadkit.contracts.data.sql.sql import (
        InvalidIdentifierError,
        RawSQL,
    )
    from quadkit.contracts.data.sql.sql_dialect import SQLDialect
    from quadkit.sql.audit.mixin import AuditRepositoryMixin
    from quadkit.sql.config import DatabaseConfig
    from quadkit.sql.context import (
        DbContext,
        RequestContextManager,
        create_db_context,
        create_task_with_context,
        run_in_threadpool_with_context,
    )
    from quadkit.sql.di.provider import DatabaseProvider
    from quadkit.sql.exceptions import (
        DatabaseError,
        OptimisticLockError,
        RepositoryError,
    )
    from quadkit.sql.identifiers import (
        Column,
        Identifier,
        QualifiedTable,
        Schema,
        Table,
        column,
        schema,
        table,
    )
    from quadkit.sql.monitoring.database_monitor import DatabaseMonitor
    from quadkit.sql.providers import (
        AbstractConnectionPool,
        ConsoleQueryLogger,
        DatabaseService,
        FileQueryLogger,
        MemoryQueryLogger,
        MySQLProvider,
        PostgresProvider,
        QueryLoggerBase,
        SimpleConnectionPool,
        SimpleMigrationManager,
        SQLiteProvider,
    )
    from quadkit.sql.query import AsyncQueryBuilder, Operator
    from quadkit.sql.repositories import F, Filter, field
    from quadkit.sql.repositories.base import (  # type: ignore[attr-defined]
        RepositoryProtocol,
    )
    from quadkit.sql.repositories.generic_repository import GenericRepository
    from quadkit.sql.resilience import DatabaseResilienceHandler
    from quadkit.sql.row_level_security import (
        NoSecurityPolicyError,
        RowLevelSecurityPolicy,
        ScopeColumn,
    )
    from quadkit.sql.search import (
        FTSDialect,
        FTSResult,
        MySQLFTSQuery,
        PostgresFTSQuery,
        full_text_search,
    )
    from quadkit.sql.stores import (
        DatabaseLockStore,
        DatabaseSecretStore,
        DatabaseStateStore,
    )
    from quadkit.sql.types import Entity
    from quadkit.sql.unit_of_work.manager import (
        SimpleTransactionManager,
        transaction,
    )
    from quadkit.sql.unit_of_work.simple import (
        SimpleUnitOfWork,
        unit_of_work,
    )

_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "HealthStatus": ("quadkit.contracts.core", "HealthStatus"),
    "HealthCheckResult": ("quadkit.contracts.core", "HealthCheckResult"),
    # Contracts
    "ConnectionPoolProtocol": ("quadkit.contracts.data", "ConnectionPoolProtocol"),
    "DatabaseProviderProtocol": ("quadkit.contracts.data", "DatabaseProviderProtocol"),
    "DeleteResult": ("quadkit.contracts.data", "DeleteResult"),
    "InsertResult": ("quadkit.contracts.data", "InsertResult"),
    "QueryLogEntry": ("quadkit.contracts.data", "QueryLogEntry"),
    "QueryLoggerProtocol": ("quadkit.contracts.data", "QueryLoggerProtocol"),
    "QueryResult": ("quadkit.contracts.data", "QueryResult"),
    "UpdateResult": ("quadkit.contracts.data", "UpdateResult"),
    # Internal - lazy loaded to avoid circular imports
    "AuditEntry": ("quadkit.contracts.audit", "AuditEntry"),
    "AuditRepositoryMixin": ("quadkit.sql.audit.mixin", "AuditRepositoryMixin"),
    "AsyncQueryBuilder": ("quadkit.sql.query", "AsyncQueryBuilder"),
    "DatabaseConfig": ("quadkit.sql.config", "DatabaseConfig"),
    "DatabaseError": ("quadkit.sql.exceptions", "DatabaseError"),
    "DatabaseModule": ("quadkit.sql.module", "DatabaseModule"),
    "DatabaseProvider": ("quadkit.sql.di.provider", "DatabaseProvider"),
    "DatabaseMonitor": ("quadkit.sql.monitoring.database_monitor", "DatabaseMonitor"),
    "DatabaseService": ("quadkit.sql.providers", "DatabaseService"),
    "Entity": ("quadkit.sql.types", "Entity"),
    "F": ("quadkit.sql.repositories", "F"),
    "Filter": ("quadkit.sql.repositories", "Filter"),
    "GenericRepository": (
        "quadkit.sql.repositories.generic_repository",
        "GenericRepository",
    ),
    "NoSecurityPolicyError": (
        "quadkit.sql.row_level_security",
        "NoSecurityPolicyError",
    ),
    "RepositoryProtocol": ("quadkit.contracts.data", "RepositoryProtocol"),
    "RowLevelSecurityPolicy": (
        "quadkit.sql.row_level_security",
        "RowLevelSecurityPolicy",
    ),
    "ScopeColumn": ("quadkit.sql.row_level_security", "ScopeColumn"),
    "OptimisticLockError": ("quadkit.sql.exceptions", "OptimisticLockError"),
    "RepositoryError": ("quadkit.sql.exceptions", "RepositoryError"),
    "SimpleUnitOfWork": ("quadkit.sql.unit_of_work.simple", "SimpleUnitOfWork"),
    "SimpleTransactionManager": (
        "quadkit.sql.unit_of_work.manager",
        "SimpleTransactionManager",
    ),
    "transaction": ("quadkit.sql.unit_of_work.manager", "transaction"),
    "unit_of_work": ("quadkit.sql.unit_of_work.simple", "unit_of_work"),
    # Implementations re-exported from providers
    "AbstractConnectionPool": ("quadkit.sql.providers", "AbstractConnectionPool"),
    "SimpleConnectionPool": ("quadkit.sql.providers", "SimpleConnectionPool"),
    "QueryLoggerBase": ("quadkit.sql.providers", "QueryLoggerBase"),
    "ConsoleQueryLogger": ("quadkit.sql.providers", "ConsoleQueryLogger"),
    "FileQueryLogger": ("quadkit.sql.providers", "FileQueryLogger"),
    "MemoryQueryLogger": ("quadkit.sql.providers", "MemoryQueryLogger"),
    "SimpleMigrationManager": ("quadkit.sql.providers", "SimpleMigrationManager"),
    "SQLiteProvider": ("quadkit.sql.providers", "SQLiteProvider"),
    "Operator": ("quadkit.sql.query", "Operator"),
    "PostgresProvider": ("quadkit.sql.providers", "PostgresProvider"),
    "MySQLProvider": ("quadkit.sql.providers", "MySQLProvider"),
    # SQL identifiers - type-safe SQL construction (moved to quadkit-sql)
    "Table": ("quadkit.sql.identifiers", "Table"),
    "Column": ("quadkit.sql.identifiers", "Column"),
    "Schema": ("quadkit.sql.identifiers", "Schema"),
    "Identifier": ("quadkit.sql.identifiers", "Identifier"),
    "QualifiedTable": ("quadkit.sql.identifiers", "QualifiedTable"),
    # SQL exceptions (still in contracts)
    "InvalidIdentifierError": (
        "quadkit.contracts.data.sql.sql",
        "InvalidIdentifierError",
    ),
    "RawSQL": ("quadkit.contracts.data.sql.sql", "RawSQL"),
    "SQLDialect": ("quadkit.contracts.data.sql.sql_dialect", "SQLDialect"),
    # Factory functions (moved to quadkit-sql)
    "table": ("quadkit.sql.identifiers", "table"),
    "column": ("quadkit.sql.identifiers", "column"),
    "schema": ("quadkit.sql.identifiers", "schema"),
    # Database-backed persistent stores (moved from quadkit-cache)
    "DatabaseStateStore": ("quadkit.sql.stores", "DatabaseStateStore"),
    "DatabaseSecretStore": ("quadkit.sql.stores", "DatabaseSecretStore"),
    "DatabaseLockStore": ("quadkit.sql.stores", "DatabaseLockStore"),
    # Context management (P0)
    "DbContext": ("quadkit.sql.context", "DbContext"),
    "create_db_context": ("quadkit.sql.context", "create_db_context"),
    "RequestContextManager": ("quadkit.sql.context", "RequestContextManager"),
    "create_task_with_context": ("quadkit.sql.context", "create_task_with_context"),
    "field": ("quadkit.sql.repositories", "field"),
    "run_in_threadpool_with_context": (
        "quadkit.sql.context",
        "run_in_threadpool_with_context",
    ),
    # Resilience (P0)
    "DatabaseResilienceHandler": (
        "quadkit.sql.resilience",
        "DatabaseResilienceHandler",
    ),
    # Full-text search utilities (P1)
    "FTSDialect": ("quadkit.sql.search", "FTSDialect"),
    "FTSResult": ("quadkit.sql.search", "FTSResult"),
    "PostgresFTSQuery": ("quadkit.sql.search", "PostgresFTSQuery"),
    "MySQLFTSQuery": ("quadkit.sql.search", "MySQLFTSQuery"),
    "full_text_search": ("quadkit.sql.search", "full_text_search"),
    # Hooks
    "SQLConnectionReadyHook": ("quadkit.sql.hooks", "SQLConnectionReadyHook"),
    "SQLTransactionBegunHook": ("quadkit.sql.hooks", "SQLTransactionBegunHook"),
    "SQLTransactionEndedHook": ("quadkit.sql.hooks", "SQLTransactionEndedHook"),
}


def __getattr__(name: str) -> Any:
    """Lazy load attributes to avoid circular imports, with caching."""
    if name in _LAZY_IMPORTS:
        import importlib

        module_path, attr_name = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value  # Cache for subsequent access
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """List available attributes for IDE support."""
    return list(__all__) + list(_LAZY_IMPORTS.keys())


__all__ = [
    "AbstractConnectionPool",
    "AuditEntry",
    "AuditRepositoryMixin",
    "Column",
    "ConnectionPoolProtocol",
    "ConsoleQueryLogger",
    "DatabaseConfig",
    "DatabaseError",
    "DatabaseLockStore",
    "DatabaseModule",
    "DatabaseMonitor",
    "DatabaseProvider",
    "DatabaseProviderProtocol",
    "DatabaseResilienceHandler",
    "DatabaseSecretStore",
    "DatabaseService",
    "DatabaseStateStore",
    "DbContext",
    "DeleteResult",
    "Entity",
    "F",
    "FTSDialect",
    "FTSResult",
    "FileQueryLogger",
    "Filter",
    "GenericRepository",
    "HealthCheckResult",
    "HealthStatus",
    "Identifier",
    "InsertResult",
    "InvalidIdentifierError",
    "MemoryQueryLogger",
    "MySQLFTSQuery",
    "MySQLProvider",
    "NoSecurityPolicyError",
    "OptimisticLockError",
    "PostgresFTSQuery",
    "PostgresProvider",
    "QualifiedTable",
    "QueryLogEntry",
    "QueryLoggerBase",
    "QueryLoggerProtocol",
    "QueryResult",
    "RawSQL",
    "RepositoryError",
    "RepositoryProtocol",
    "RequestContextManager",
    "RowLevelSecurityPolicy",
    "SQLConnectionReadyHook",
    "SQLDialect",
    "SQLTransactionBegunHook",
    "SQLTransactionEndedHook",
    "SQLiteProvider",
    "Schema",
    "ScopeColumn",
    "SimpleConnectionPool",
    "SimpleMigrationManager",
    "SimpleTransactionManager",
    "SimpleUnitOfWork",
    "Table",
    "UpdateResult",
    "column",
    "create_db_context",
    "create_task_with_context",
    "field",
    "full_text_search",
    "run_in_threadpool_with_context",
    "schema",
    "table",
    "transaction",
    "unit_of_work",
]
