"""Field type mapping for the declarative schema model system.

Defines :class:`FieldType` and the Python-type → SQL-type mappings used
by :class:`~quadkit.sql.schema.model.Field`.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID


class FieldType(StrEnum):
    """Supported database field types for cross-dialect mapping."""

    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    BIGINT = "bigint"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    UUID = "uuid"
    JSON = "json"
    JSONB = "jsonb"
    BINARY = "binary"
    ARRAY = "array"


# Python type → FieldType mapping
_TYPE_MAP: dict[type, FieldType] = {
    str: FieldType.STRING,
    int: FieldType.INTEGER,
    float: FieldType.FLOAT,
    bool: FieldType.BOOLEAN,
    datetime: FieldType.DATETIME,
    UUID: FieldType.UUID,
    bytes: FieldType.BINARY,
    dict: FieldType.JSON,
    list: FieldType.ARRAY,
}


def _get_sql_type(
    ft: FieldType,
    max_length: int | None,
    dialect: str,
) -> str:
    """Map FieldType to SQL type for a given dialect."""
    pg_map = {
        FieldType.STRING: f"VARCHAR({max_length or 255})",
        FieldType.TEXT: "TEXT",
        FieldType.INTEGER: "INTEGER",
        FieldType.BIGINT: "BIGINT",
        FieldType.FLOAT: "DOUBLE PRECISION",
        FieldType.DECIMAL: "NUMERIC",
        FieldType.BOOLEAN: "BOOLEAN",
        FieldType.DATE: "DATE",
        FieldType.DATETIME: "TIMESTAMP WITHOUT TIME ZONE",
        FieldType.TIMESTAMP: "TIMESTAMP WITH TIME ZONE",
        FieldType.UUID: "UUID",
        FieldType.JSON: "JSON",
        FieldType.JSONB: "JSONB",
        FieldType.BINARY: "BYTEA",
        FieldType.ARRAY: "TEXT[]",
    }
    mysql_map = {
        FieldType.STRING: f"VARCHAR({max_length or 255})",
        FieldType.TEXT: "TEXT",
        FieldType.INTEGER: "INT",
        FieldType.BIGINT: "BIGINT",
        FieldType.FLOAT: "DOUBLE",
        FieldType.DECIMAL: "DECIMAL",
        FieldType.BOOLEAN: "TINYINT(1)",
        FieldType.DATE: "DATE",
        FieldType.DATETIME: "DATETIME",
        FieldType.TIMESTAMP: "TIMESTAMP",
        FieldType.UUID: "CHAR(36)",
        FieldType.JSON: "JSON",
        FieldType.JSONB: "JSON",
        FieldType.BINARY: "BLOB",
        FieldType.ARRAY: "JSON",
    }
    sqlite_map = {
        FieldType.STRING: "TEXT",
        FieldType.TEXT: "TEXT",
        FieldType.INTEGER: "INTEGER",
        FieldType.BIGINT: "INTEGER",
        FieldType.FLOAT: "REAL",
        FieldType.DECIMAL: "REAL",
        FieldType.BOOLEAN: "INTEGER",
        FieldType.DATE: "TEXT",
        FieldType.DATETIME: "TEXT",
        FieldType.TIMESTAMP: "TEXT",
        FieldType.UUID: "TEXT",
        FieldType.JSON: "TEXT",
        FieldType.JSONB: "TEXT",
        FieldType.BINARY: "BLOB",
        FieldType.ARRAY: "TEXT",
    }
    type_map = {
        "postgresql": pg_map,
        "mysql": mysql_map,
        "sqlite": sqlite_map,
    }
    d = type_map.get(dialect, pg_map)
    return d.get(ft, "TEXT")
