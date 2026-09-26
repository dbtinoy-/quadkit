"""Unit tests for quadkit-sql types.

These tests verify the types defined in quadkit.sql.types.
"""

from quadkit.sql.types import (
    ColumnDefinition,
    DatabaseProviderType,
    Entity,
    OrderDirection,
    QueryType,
    SchemaDiff,
    TableDefinition,
)


class TestDatabaseProviderType:
    """Tests for DatabaseProviderType enum."""

    def test_database_provider_type_sqlite_value(self) -> None:
        assert DatabaseProviderType.SQLITE.value == "sqlite"

    def test_database_provider_type_postgresql_value(self) -> None:
        assert DatabaseProviderType.POSTGRESQL.value == "postgres"

    def test_database_provider_type_mysql_value(self) -> None:
        assert DatabaseProviderType.MYSQL.value == "mysql"


class TestQueryType:
    """Tests for QueryType enum."""

    def test_query_type_select_value(self) -> None:
        assert QueryType.SELECT.value == "SELECT"

    def test_query_type_insert_value(self) -> None:
        assert QueryType.INSERT.value == "INSERT"

    def test_query_type_update_value(self) -> None:
        assert QueryType.UPDATE.value == "UPDATE"

    def test_query_type_delete_value(self) -> None:
        assert QueryType.DELETE.value == "DELETE"


class TestOrderDirection:
    """Tests for OrderDirection enum."""

    def test_order_direction_asc_value(self) -> None:
        assert OrderDirection.ASC.value == "ASC"

    def test_order_direction_desc_value(self) -> None:
        assert OrderDirection.DESC.value == "DESC"


class TestColumnDefinition:
    """Tests for ColumnDefinition dataclass."""

    def test_column_definition_creation(self) -> None:
        col = ColumnDefinition(name="id", type_sql="INTEGER")
        assert col.name == "id"
        assert col.type_sql == "INTEGER"

    def test_column_definition_defaults(self) -> None:
        col = ColumnDefinition(name="name", type_sql="VARCHAR")
        assert col.nullable is True
        assert col.default is None
        assert col.primary_key is False
        assert col.unique is False
        assert col.index is False

    def test_column_definition_with_options(self) -> None:
        col = ColumnDefinition(
            name="id",
            type_sql="INTEGER",
            nullable=False,
            default=0,
            primary_key=True,
            unique=True,
            index=True,
            length=255,
        )
        assert col.nullable is False
        assert col.default == 0
        assert col.primary_key is True
        assert col.unique is True
        assert col.index is True
        assert col.length == 255


class TestTableDefinition:
    """Tests for TableDefinition dataclass."""

    def test_table_definition_creation(self) -> None:
        cols = [ColumnDefinition(name="id", type_sql="INTEGER")]
        table = TableDefinition(name="users", columns=cols)
        assert table.name == "users"
        assert table.columns == cols

    def test_table_definition_defaults(self) -> None:
        table = TableDefinition(name="users", columns=[])
        assert table.indexes == []
        assert table.constraints == []


class TestSchemaDiff:
    """Tests for SchemaDiff dataclass."""

    def test_schema_diff_creation(self) -> None:
        tables_to_create = [TableDefinition(name="users", columns=[])]
        tables_to_drop = ["old_table"]
        columns_to_add = {"users": [ColumnDefinition(name="email", type_sql="VARCHAR")]}
        columns_to_drop = {"users": ["old_column"]}
        columns_to_modify = {}
        indexes_to_add = {}
        indexes_to_drop = {}

        diff = SchemaDiff(
            tables_to_create=tables_to_create,
            tables_to_drop=tables_to_drop,
            columns_to_add=columns_to_add,
            columns_to_drop=columns_to_drop,
            columns_to_modify=columns_to_modify,
            indexes_to_add=indexes_to_add,
            indexes_to_drop=indexes_to_drop,
        )
        assert diff.tables_to_create == tables_to_create
        assert diff.tables_to_drop == tables_to_drop


class TestEntity:
    """Tests for Entity base class."""

    def test_entity_get_table_name_default(self) -> None:
        class User(Entity):
            pass

        assert User.get_table_name() == "users"

    def test_entity_get_table_name_custom(self) -> None:
        class User(Entity):
            __tablename__ = "custom_users"

        assert User.get_table_name() == "custom_users"

    def test_entity_to_dict(self) -> None:
        class User(Entity):
            def __init__(self, name: str):
                self.name = name

        user = User(name="John")
        result = user.to_dict()
        assert "name" in result

    def test_entity_from_dict(self) -> None:
        class User(Entity):
            def __init__(self, name: str):
                self.name = name

        user = User.from_dict({"name": "John"})
        assert user.name == "John"


class TestAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_expected_types(self) -> None:
        from quadkit.sql import types as type_module

        expected = [
            "ColumnDefinition",
            "DatabaseProviderType",
            "Entity",
            "OrderDirection",
            "QueryType",
            "SchemaDiff",
            "TableDefinition",
        ]
        for item in expected:
            assert item in type_module.__all__
