"""Unit tests for quadkit.sql.types module"""

from __future__ import annotations

import pytest

from quadkit.sql.types import (
    ColumnDefinition,
    TableDefinition,
    SchemaDiff,
    DatabaseProviderType,
    QueryType,
    OrderDirection,
    Entity,
    IsolationLevel,
    JoinType,
    WhereOperator,
    MigrationInfo,
    MigrationStatus,
)


class TestDatabaseProviderType:
    def test_enum_values(self) -> None:
        assert DatabaseProviderType.SQLITE == "sqlite"
        assert DatabaseProviderType.POSTGRESQL == "postgres"
        assert DatabaseProviderType.MYSQL == "mysql"

    def test_enum_is_str_enum(self) -> None:
        assert isinstance(DatabaseProviderType.SQLITE, str)

    def test_all_values_accessible(self) -> None:
        values = list(DatabaseProviderType)
        assert len(values) == 3


class TestQueryType:
    def test_enum_values(self) -> None:
        assert QueryType.SELECT == "SELECT"
        assert QueryType.INSERT == "INSERT"
        assert QueryType.UPDATE == "UPDATE"
        assert QueryType.DELETE == "DELETE"

    def test_enum_is_str_enum(self) -> None:
        assert isinstance(QueryType.SELECT, str)


class TestOrderDirection:
    def test_enum_values(self) -> None:
        assert OrderDirection.ASC == "ASC"
        assert OrderDirection.DESC == "DESC"

    def test_enum_is_str_enum(self) -> None:
        assert isinstance(OrderDirection.ASC, str)


class TestColumnDefinition:
    def test_basic_creation(self) -> None:
        col = ColumnDefinition(name="id", type_sql="INTEGER")
        assert col.name == "id"
        assert col.type_sql == "INTEGER"
        assert col.nullable is True

    def test_primary_key_column(self) -> None:
        col = ColumnDefinition(
            name="id", type_sql="INTEGER", nullable=False, primary_key=True
        )
        assert col.primary_key is True
        assert col.nullable is False

    def test_column_with_defaults(self) -> None:
        col = ColumnDefinition(
            name="created_at",
            type_sql="TIMESTAMP",
            nullable=False,
            default="CURRENT_TIMESTAMP",
            index=True,
        )
        assert col.default == "CURRENT_TIMESTAMP"
        assert col.index is True

    def test_column_with_foreign_key(self) -> None:
        col = ColumnDefinition(
            name="user_id", type_sql="INTEGER", foreign_key="users(id)"
        )
        assert col.foreign_key == "users(id)"

    def test_column_with_length(self) -> None:
        col = ColumnDefinition(name="username", type_sql="VARCHAR", length=255)
        assert col.length == 255


class TestTableDefinition:
    def test_basic_creation(self) -> None:
        table = TableDefinition(
            name="users",
            columns=[
                ColumnDefinition(name="id", type_sql="INTEGER", primary_key=True),
                ColumnDefinition(name="email", type_sql="VARCHAR"),
            ],
        )
        assert table.name == "users"
        assert len(table.columns) == 2

    def test_with_indexes(self) -> None:
        table = TableDefinition(
            name="users",
            columns=[ColumnDefinition(name="id", type_sql="INTEGER")],
            indexes=[{"name": "idx_email", "columns": ["email"]}],
        )
        assert len(table.indexes) == 1

    def test_with_constraints(self) -> None:
        table = TableDefinition(
            name="users",
            columns=[ColumnDefinition(name="id", type_sql="INTEGER")],
            constraints=[{"type": "unique", "columns": ["email"]}],
        )
        assert len(table.constraints) == 1


class TestSchemaDiff:
    def test_empty_diff(self) -> None:
        diff = SchemaDiff(
            tables_to_create=[],
            tables_to_drop=[],
            columns_to_add={},
            columns_to_drop={},
            columns_to_modify={},
            indexes_to_add={},
            indexes_to_drop={},
        )
        assert diff.tables_to_create == []
        assert diff.tables_to_drop == []

    def test_with_changes(self) -> None:
        diff = SchemaDiff(
            tables_to_create=[
                TableDefinition(
                    name="new_table",
                    columns=[ColumnDefinition(name="id", type_sql="INTEGER")],
                )
            ],
            tables_to_drop=["old_table"],
            columns_to_add={"users": [ColumnDefinition(name="new_col", type_sql="TEXT")]},
            columns_to_drop={"users": ["old_col"]},
            columns_to_modify={},
            indexes_to_add={},
            indexes_to_drop={},
        )
        assert len(diff.tables_to_create) == 1
        assert "old_table" in diff.tables_to_drop
        assert diff.columns_to_add["users"][0].name == "new_col"


class TestEntity:
    def test_get_table_name_default(self) -> None:
        class TestEntity(Entity):
            pass

        assert TestEntity.get_table_name() == "testentitys"

    def test_get_table_name_custom(self) -> None:
        class User(Entity):
            __tablename__ = "users"

        assert User.get_table_name() == "users"

    def test_to_dict(self) -> None:
        class Person(Entity):
            def __init__(self, name: str, age: int) -> None:
                self.name = name
                self.age = age

        person = Person(name="Alice", age=30)
        result = person.to_dict()
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_from_dict(self) -> None:
        class Person(Entity):
            def __init__(self, name: str, age: int) -> None:
                self.name = name
                self.age = age

        data = {"name": "Bob", "age": 25}
        person = Person.from_dict(data)
        assert person.name == "Bob"
        assert person.age == 25


class TestTypeAliases:
    def test_type_aliases_exist(self) -> None:
        from quadkit.sql.types import (
            ConnectionString,
            SQLQuery,
            QueryParams,
            TableName,
            ColumnName,
            DatabaseURL,
            QueryRows,
            PoolStats,
            DatabaseStats,
            ConfigMapping,
            EnvironmentVariables,
            PaginationResult,
            MigrationScript,
            MigrationVersion,
            LogLevel,
            LogEntry,
            ErrorMessage,
            ErrorCode,
            RepositoryResult,
            TEntity,
            TKey,
        )

        assert ConnectionString == str
        assert SQLQuery == str
        assert TableName == str
        assert ColumnName == str
        assert DatabaseURL == str
        assert LogLevel == str
        assert ErrorMessage == str
        assert ErrorCode == str
        assert TEntity.__name__ == "TEntity"
        assert TKey.__name__ == "TKey"


class TestImportedTypes:
    def test_isolation_level_from_contracts(self) -> None:
        assert IsolationLevel.READ_COMMITTED == "READ COMMITTED"
        assert IsolationLevel.REPEATABLE_READ == "REPEATABLE READ"

    def test_join_type_enum(self) -> None:
        assert JoinType.INNER == "INNER"
        assert JoinType.LEFT == "LEFT"

    def test_where_operator_enum(self) -> None:
        assert WhereOperator.EQ == "="
        assert WhereOperator.NE == "!="
        assert WhereOperator.GT == ">"
        assert WhereOperator.GE == ">="
        assert WhereOperator.LT == "<"
        assert WhereOperator.LE == "<="

    def test_migration_status_is_dataclass(self) -> None:
        status = MigrationStatus(
            current_revision="001",
            head_revision="001",
            is_up_to_date=True,
            pending_migrations=[],
        )
        assert status.current_revision == "001"
        assert status.is_up_to_date is True

    def test_migration_info_exists(self) -> None:
        info = MigrationInfo(
            revision="001", version="1.0", description="Initial"
        )
        assert info.revision == "001"