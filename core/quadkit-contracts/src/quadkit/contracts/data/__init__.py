"""Data access protocols."""

from __future__ import annotations

from quadkit.contracts.data.aggregatable import AggregatableProtocol
from quadkit.contracts.data.bulk_operations import BulkOperationsProtocol
from quadkit.contracts.data.data_source import DataSourceProtocol
from quadkit.contracts.data.exceptions import UnitOfWorkError
from quadkit.contracts.data.graph.protocols import GraphProtocol, GraphStoreProtocol
from quadkit.contracts.data.graph.types import (
    GraphEdge,
    GraphInfo,
    GraphNode,
    GraphPath,
)
from quadkit.contracts.data.identifiers import (
    DEFAULT_MAX_IDENTIFIER_LENGTH,
    MAX_IDENTIFIER_LENGTHS,
    Column,
    Identifier,
    QualifiedTable,
    Schema,
    Table,
    column,
    schema,
    table,
)
from quadkit.contracts.data.nosql.nosql import (
    BulkWriteResult,
    CollectionProtocol,
    DocumentResult,
    DocumentStoreProtocol,
)
from quadkit.contracts.data.nosql.nosql_repository import DocumentRepositoryProtocol
from quadkit.contracts.data.outbox import OutboxStoreProtocol
from quadkit.contracts.data.protocols import (
    AndExpr,
    CursorCodecProtocol,
    CursorPaginationSpec,
    FieldContains,
    FieldEq,
    FieldGt,
    FieldGte,
    FieldIn,
    FieldLt,
    FieldLte,
    FieldNeq,
    FilterCompilerProtocol,
    FilterExpression,
    NotExpr,
    OrExpr,
    PaginationSpec,
    PaginatorProtocol,
    ProjectionSpec,
    QueryFilterProtocol,
    SortSpecification,
)
from quadkit.contracts.data.relation_loader import RelationLoaderProtocol
from quadkit.contracts.data.repository import (
    ReadOnlyRepositoryProtocol,
    RepositoryProtocol,
)
from quadkit.contracts.data.searchable import SearchableProtocol
from quadkit.contracts.data.sql.append_log import (
    AppendLogProtocol,
    AppendLogSnapshotStore,
)
from quadkit.contracts.data.sql.context_protocol import DatabaseContextProtocol
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
from quadkit.contracts.data.sql.migrations import MigrationRunnerProtocol
from quadkit.contracts.data.sql.query_log import QueryLogEntry, QueryLoggerProtocol
from quadkit.contracts.data.sql.sql import InvalidIdentifierError, RawSQL
from quadkit.contracts.data.sql.sql_dialect import SQLDialect
from quadkit.contracts.data.sql.unit_of_work import UnitOfWorkProtocol
from quadkit.contracts.data.timeseries import TimeSeriesStoreProtocol
from quadkit.contracts.data.vector.protocols import (
    VectorCollectionProtocol,
    VectorStoreProtocol,
)
from quadkit.contracts.data.vector.types import (
    CollectionConfig,
    CollectionInfo,
    SearchQuery,
    SearchResult,
    VectorRecord,
)

__all__ = [
    "DEFAULT_MAX_IDENTIFIER_LENGTH",
    "MAX_IDENTIFIER_LENGTHS",
    "AggregatableProtocol",
    "AndExpr",
    "AppendLogProtocol",
    "AppendLogSnapshotStore",
    "BulkOperationsProtocol",
    "BulkWriteResult",
    "CollectionConfig",
    "CollectionInfo",
    "CollectionProtocol",
    "Column",
    "ConnectionPoolProtocol",
    "ConnectionProtocol",
    "CrudOperationsProtocol",
    "CursorCodecProtocol",
    "CursorPaginationSpec",
    "DataMapperProtocol",
    "DataSourceProtocol",
    "DatabaseMetricsProtocol",
    "DatabaseProviderProtocol",
    "DeleteResult",
    "DocumentRepositoryProtocol",
    "DocumentResult",
    "DocumentStoreProtocol",
    "FieldContains",
    "FieldEq",
    "FieldGt",
    "FieldGte",
    "FieldIn",
    "FieldLt",
    "FieldLte",
    "FieldNeq",
    "FilterCompilerProtocol",
    "FilterExpression",
    "GraphEdge",
    "GraphInfo",
    "GraphNode",
    "GraphPath",
    "GraphProtocol",
    "GraphStoreProtocol",
    "HealthMonitorProtocol",
    "Identifier",
    "InsertResult",
    "InvalidIdentifierError",
    "IsolationLevel",
    "MigrationManagerProtocol",
    "MigrationRecord",
    "NotExpr",
    "OrExpr",
    "OutboxStoreProtocol",
    "PaginationSpec",
    "PaginatorProtocol",
    "ProjectionSpec",
    "QualifiedTable",
    "QueryFilterProtocol",
    "QueryLogEntry",
    "QueryLoggerProtocol",
    "QueryResult",
    "RawSQL",
    "ReadOnlyMapperProtocol",
    "ReadOnlyRepositoryProtocol",
    "RelationLoaderProtocol",
    "RepositoryProtocol",
    "SQLDialect",
    "Schema",
    "SchemaManagerProtocol",
    "SearchQuery",
    "SearchResult",
    "SearchableProtocol",
    "SortSpecification",
    "Table",
    "TimeSeriesStoreProtocol",
    "TransactionManagerProtocol",
    "UnitOfWorkError",
    "UnitOfWorkProtocol",
    "UpdateResult",
    "VectorCollectionProtocol",
    "VectorRecord",
    "VectorStoreProtocol",
    "column",
    "schema",
    "table",
]
