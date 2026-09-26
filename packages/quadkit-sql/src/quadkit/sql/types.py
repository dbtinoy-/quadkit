"""Type definitions and data structures for Quadkit DB"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeAlias, TypeVar

from quadkit.contracts.core import JSON, HealthStatus
from quadkit.contracts.data.sql.database import IsolationLevel
from quadkit.domain import DomainModel
from quadkit.validation import ConfigDict

# Generic type variables
TEntity = TypeVar("TEntity")
TKey = TypeVar("TKey")


class DatabaseProviderType(StrEnum):
    """Supported database provider types"""

    SQLITE = "sqlite"
    POSTGRESQL = "postgres"
    MYSQL = "mysql"


# IsolationLevel is imported from quadkit.contracts.data.sql.database and re-exported below.


class QueryType(StrEnum):
    """Types of database queries"""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class OrderDirection(StrEnum):
    """Query ordering directions"""

    ASC = "ASC"
    DESC = "DESC"


# Use canonical JoinType and Operator from the merged query package modules.
from quadkit.sql.query.operators import Operator as WhereOperator
from quadkit.sql.query.sql_types import JoinType


@dataclass
class ColumnDefinition:
    """Database column definition."""

    name: str
    type_sql: str
    nullable: bool = True
    default: Any | None = None
    primary_key: bool = False
    unique: bool = False
    index: bool = False
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    foreign_key: str | None = None
    comment: str | None = None


@dataclass
class TableDefinition:
    """Database table definition."""

    name: str
    columns: list[ColumnDefinition]
    indexes: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SchemaDiff:
    """Schema difference between current and target state."""

    tables_to_create: list[TableDefinition]
    tables_to_drop: list[str]
    columns_to_add: dict[str, list[ColumnDefinition]]
    columns_to_drop: dict[str, list[str]]
    columns_to_modify: dict[str, list[dict[str, Any]]]
    indexes_to_add: dict[str, list[dict[str, Any]]]
    indexes_to_drop: dict[str, list[str]]
    constraints_to_add: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    constraints_to_drop: dict[str, list[str]] = field(default_factory=dict)


# Use canonical MigrationInfo and MigrationStatus from migrations/types.py
from quadkit.sql.migrations.types import MigrationInfo, MigrationStatus

# Type aliases
ConnectionString = str
SQLQuery = str
QueryParams = list[Any] | None
TableName = str
ColumnName = str
DatabaseURL = str

# Result types
QueryRows = list[dict[str, Any]]
# Import unified types from core quadkit

PoolStats = JSON
DatabaseStats = JSON

# Configuration types
ConfigMapping = JSON
EnvironmentVariables = dict[str, str]

# RepositoryProtocol types
RepositoryResult: TypeAlias = TEntity | list[TEntity] | int | bool
PaginationResult = dict[str, Any]

# Migration types
MigrationScript = str
MigrationVersion = str

# Logging types
LogLevel = str
LogEntry = dict[str, Any]

# Error types
ErrorMessage = str
ErrorCode = str


# Entity base class
@dataclass(init=False)
class Entity(DomainModel):
    """Simple entity base class using Domain models from contracts.

    This replaces the complex ORM Model metaclass with a clean,
    simple base class for domain entities.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, from_attributes=True)

    @classmethod
    def get_table_name(cls) -> str:
        """Get the table name for this entity."""
        table_name_attr = getattr(cls, "__tablename__", None)
        if table_name_attr:
            return str(table_name_attr)
        return cls.__name__.lower() + "s"

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Entity:
        """Create entity from dictionary."""
        return cls(**data)


__all__ = [
    # Data classes
    "ColumnDefinition",
    "ColumnName",
    "ConfigMapping",
    # Type aliases
    "ConnectionString",
    # Enums
    "DatabaseProviderType",
    "DatabaseStats",
    "DatabaseURL",
    # Classes
    "Entity",
    "EnvironmentVariables",
    "ErrorCode",
    "ErrorMessage",
    "HealthStatus",
    "IsolationLevel",
    "JoinType",
    "LogEntry",
    "LogLevel",
    "MigrationInfo",
    "MigrationScript",
    "MigrationStatus",
    "MigrationVersion",
    "OrderDirection",
    "PaginationResult",
    "PoolStats",
    "QueryParams",
    "QueryRows",
    "QueryType",
    "RepositoryResult",
    "SQLQuery",
    "SchemaDiff",
    # Type variables
    "TEntity",
    "TKey",
    "TableDefinition",
    "TableName",
    "WhereOperator",
]
