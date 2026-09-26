"""Tests for schema field type mapping (FieldType, Python→SQL per dialect)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from quadkit.sql.schema.field_types import (
    _TYPE_MAP,
    FieldType,
    _get_sql_type,
)
from quadkit.sql.schema.model import Field


class TestTypeMap:
    def test_python_type_mapping(self) -> None:
        assert _TYPE_MAP[str] == FieldType.STRING
        assert _TYPE_MAP[int] == FieldType.INTEGER
        assert _TYPE_MAP[float] == FieldType.FLOAT
        assert _TYPE_MAP[bool] == FieldType.BOOLEAN
        assert _TYPE_MAP[datetime] == FieldType.DATETIME
        assert _TYPE_MAP[UUID] == FieldType.UUID
        assert _TYPE_MAP[bytes] == FieldType.BINARY
        assert _TYPE_MAP[dict] == FieldType.JSON
        assert _TYPE_MAP[list] == FieldType.ARRAY

    def test_is_strenum(self) -> None:
        assert FieldType.STRING == "string"
        assert FieldType.JSONB == "jsonb"


class TestPostgresMapping:
    def test_string_default_length(self) -> None:
        assert _get_sql_type(FieldType.STRING, None, "postgresql") == "VARCHAR(255)"

    def test_string_custom_length(self) -> None:
        assert _get_sql_type(FieldType.STRING, 100, "postgresql") == "VARCHAR(100)"

    def test_float_decimal_uuid(self) -> None:
        assert _get_sql_type(FieldType.FLOAT, None, "postgresql") == "DOUBLE PRECISION"
        assert _get_sql_type(FieldType.DECIMAL, None, "postgresql") == "NUMERIC"
        assert _get_sql_type(FieldType.UUID, None, "postgresql") == "UUID"

    def test_datetime_vs_timestamp(self) -> None:
        assert (
            _get_sql_type(FieldType.DATETIME, None, "postgresql")
            == "TIMESTAMP WITHOUT TIME ZONE"
        )
        assert (
            _get_sql_type(FieldType.TIMESTAMP, None, "postgresql")
            == "TIMESTAMP WITH TIME ZONE"
        )

    def test_binary_json_array(self) -> None:
        assert _get_sql_type(FieldType.BINARY, None, "postgresql") == "BYTEA"
        assert _get_sql_type(FieldType.JSONB, None, "postgresql") == "JSONB"
        assert _get_sql_type(FieldType.ARRAY, None, "postgresql") == "TEXT[]"


class TestMySQLMapping:
    def test_scalar_types(self) -> None:
        assert _get_sql_type(FieldType.INTEGER, None, "mysql") == "INT"
        assert _get_sql_type(FieldType.FLOAT, None, "mysql") == "DOUBLE"
        assert _get_sql_type(FieldType.DECIMAL, None, "mysql") == "DECIMAL"
        assert _get_sql_type(FieldType.BOOLEAN, None, "mysql") == "TINYINT(1)"

    def test_uuid_and_array(self) -> None:
        assert _get_sql_type(FieldType.UUID, None, "mysql") == "CHAR(36)"
        assert _get_sql_type(FieldType.ARRAY, None, "mysql") == "JSON"
        assert _get_sql_type(FieldType.BINARY, None, "mysql") == "BLOB"

    def test_datetime_and_timestamp(self) -> None:
        assert _get_sql_type(FieldType.DATETIME, None, "mysql") == "DATETIME"
        assert _get_sql_type(FieldType.TIMESTAMP, None, "mysql") == "TIMESTAMP"


class TestSQLiteMapping:
    def test_affinity_mapping(self) -> None:
        assert _get_sql_type(FieldType.STRING, None, "sqlite") == "TEXT"
        assert _get_sql_type(FieldType.INTEGER, None, "sqlite") == "INTEGER"
        assert _get_sql_type(FieldType.FLOAT, None, "sqlite") == "REAL"
        assert _get_sql_type(FieldType.BOOLEAN, None, "sqlite") == "INTEGER"
        assert _get_sql_type(FieldType.DATETIME, None, "sqlite") == "TEXT"
        assert _get_sql_type(FieldType.BINARY, None, "sqlite") == "BLOB"


class TestFallbacks:
    def test_unknown_dialect_defaults_to_postgres(self) -> None:
        assert _get_sql_type(FieldType.STRING, 50, "cockroachdb") == "VARCHAR(50)"
        assert _get_sql_type(FieldType.BINARY, None, "mariadb") == "BYTEA"

    def test_unknown_type_defaults_to_text(self) -> None:
        # simulate an unhandled FieldType member
        assert _get_sql_type(_TypeSentinel, None, "postgresql") == "TEXT"


class _TypeSentinel:  # not a FieldType member → dict.get fallback
    pass


class TestFieldIntegration:
    def test_field_to_sql_type_postgres(self) -> None:
        assert Field(str).to_sql_type() == "VARCHAR(255)"

    def test_field_to_sql_type_with_max_length(self) -> None:
        f = Field(str, max_length=8)
        assert f.to_sql_type("postgresql") == "VARCHAR(8)"
        assert f.to_sql_type("mysql") == "VARCHAR(8)"

    def test_field_to_sql_type_mysql(self) -> None:
        assert Field(bool).to_sql_type("mysql") == "TINYINT(1)"

    def test_field_to_sql_type_sqlite(self) -> None:
        assert Field(int).to_sql_type("sqlite") == "INTEGER"
        assert Field(dict).to_sql_type("sqlite") == "TEXT"

    def test_field_type_attr(self) -> None:
        assert Field(datetime).field_type == FieldType.DATETIME

    def test_unmapped_type_falls_back_to_string(self) -> None:
        assert Field(set).field_type == FieldType.STRING
        assert Field(set).to_sql_type() == "VARCHAR(255)"

    def test_explicit_db_type_overrides(self) -> None:
        f = Field(int, db_type="SMALLINT")
        assert f.to_sql_type("mysql") == "SMALLINT"
