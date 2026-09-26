"""Column/table definition and schema-diff tests."""

from dataclasses import dataclass
"""Unit tests for migration generator components"""

from datetime import datetime
from pathlib import Path
import tempfile

import pytest

from quadkit.domain import DomainModel
from quadkit.validation import Field

from quadkit.sql.migrations.generator import (
    ColumnDefinition,
    MigrationError,
    MigrationGenerator,
    ModelAnalyzer,
    SchemaDiff,
    TableDefinition,
)




class TestColumnDefinition:
    """Test ColumnDefinition dataclass"""

    def test_column_definition_creation(self):
        """Test creating a column definition"""
        col = ColumnDefinition(
            name="id",
            type_sql="INTEGER",
            nullable=False,
            primary_key=True,
            unique=True,
            index=True,
            foreign_key="users.id",
            comment="Primary key",
        )

        assert col.name == "id"
        assert col.type_sql == "INTEGER"
        assert col.nullable is False
        assert col.primary_key is True
        assert col.unique is True
        assert col.index is True
        assert col.foreign_key == "users.id"
        assert col.comment == "Primary key"
        assert col.default is None

    def test_column_definition_defaults(self):
        """Test column definition default values"""
        col = ColumnDefinition(name="name", type_sql="VARCHAR")

        assert col.name == "name"
        assert col.type_sql == "VARCHAR"
        assert col.nullable is True
        assert col.primary_key is False
        assert col.unique is False
        assert col.index is False
        assert col.foreign_key is None
        assert col.comment is None
        assert col.default is None


class TestTableDefinition:
    """Test TableDefinition dataclass"""

    def test_table_definition_creation(self):
        """Test creating a table definition"""
        columns = [
            ColumnDefinition(name="id", type_sql="INTEGER", primary_key=True),
            ColumnDefinition(name="name", type_sql="VARCHAR"),
        ]

        table = TableDefinition(
            name="users",
            columns=columns,
            indexes=[{"name": "ix_users_name", "columns": ["name"]}],
            constraints=[
                {
                    "name": "ck_name_length",
                    "type": "check",
                    "expression": "length(name) > 0",
                },
            ],
        )

        assert table.name == "users"
        assert len(table.columns) == 2
        assert len(table.indexes) == 1
        assert len(table.constraints) == 1

    def test_table_definition_post_init_defaults(self):
        """Test table definition post init sets defaults"""
        table = TableDefinition(name="users", columns=[])

        assert table.indexes == []
        assert table.constraints == []


class TestSchemaDiff:
    """Test SchemaDiff dataclass"""

    def test_schema_diff_creation(self):
        """Test creating a schema diff"""
        diff = SchemaDiff(
            tables_to_create=[TableDefinition(name="users", columns=[])],
            tables_to_drop=["old_table"],
            columns_to_add={
                "users": [ColumnDefinition(name="email", type_sql="VARCHAR")],
            },
            columns_to_drop={"users": ["old_column"]},
            columns_to_modify={"users": [{"name": "name", "type_sql": "VARCHAR(255)"}]},
            indexes_to_add={
                "users": [{"name": "ix_users_email", "columns": ["email"]}],
            },
            indexes_to_drop={"users": ["ix_users_old"]},
            constraints_to_add={
                "users": [{"name": "ck_email_format", "type": "check"}],
            },
            constraints_to_drop={"users": ["ck_old_constraint"]},
        )

        assert len(diff.tables_to_create) == 1
        assert diff.tables_to_drop == ["old_table"]
        assert "users" in diff.columns_to_add
        assert "users" in diff.columns_to_drop
        assert "users" in diff.columns_to_modify
        assert "users" in diff.indexes_to_add
        assert "users" in diff.indexes_to_drop
        assert "users" in diff.constraints_to_add
        assert "users" in diff.constraints_to_drop


