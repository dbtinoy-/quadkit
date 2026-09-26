"""ModelAnalyzer introspection tests."""

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




class TestModelAnalyzer:
    """Test ModelAnalyzer functionality"""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance"""
        return ModelAnalyzer()

    def test_analyzer_creation(self, analyzer):
        """Test analyzer can be created"""
        assert isinstance(analyzer, ModelAnalyzer)
        assert analyzer.TYPE_MAPPING[str] == "VARCHAR"
        assert analyzer.TYPE_MAPPING[int] == "INTEGER"
        assert analyzer.TYPE_MAPPING[bool] == "BOOLEAN"

    def test_analyze_model_basic(self, analyzer):
        """Test analyzing a basic DomainModel."""

        @dataclass
        class User(DomainModel):
            id: int
            name: str
            email: str | None = None
            active: bool = True

        table_def = analyzer.analyze_model(User)

        assert table_def.name == "user"  # snake_case conversion
        assert len(table_def.columns) == 4

        # Check id column
        id_col = next(col for col in table_def.columns if col.name == "id")
        assert id_col.type_sql == "INTEGER"
        assert id_col.primary_key is True  # id field is auto primary key
        assert id_col.nullable is False

        # Check name column
        name_col = next(col for col in table_def.columns if col.name == "name")
        assert name_col.type_sql == "VARCHAR"
        assert name_col.nullable is False

        # Check email column (optional)
        email_col = next(col for col in table_def.columns if col.name == "email")
        assert email_col.type_sql == "VARCHAR"
        assert email_col.nullable is True

        # Check active column
        active_col = next(col for col in table_def.columns if col.name == "active")
        assert active_col.type_sql == "BOOLEAN"
        assert active_col.nullable is False
        assert active_col.default == "TRUE"

    def test_analyze_model_with_meta_table_name(self, analyzer):
        """Test analyzing model with custom table name in Meta"""

        @dataclass
        class CustomUser(DomainModel):
            id: int
            name: str

            class Meta:
                table_name = "custom_users"

        table_def = analyzer.analyze_model(CustomUser)
        assert table_def.name == "custom_users"

    def test_analyze_model_with_constraints(self, analyzer):
        """Test analyzing model with field constraints"""

        @dataclass
        class User(DomainModel):
            id: int = Field(json_schema_extra={"primary_key": True})
            email: str = Field(json_schema_extra={"unique": True, "index": True})
            name: str = Field(description="User's full name")

        table_def = analyzer.analyze_model(User)

        id_col = next(col for col in table_def.columns if col.name == "id")
        assert id_col.primary_key is True

        email_col = next(col for col in table_def.columns if col.name == "email")
        assert email_col.unique is True
        assert email_col.index is True

        name_col = next(col for col in table_def.columns if col.name == "name")
        assert name_col.comment == "User's full name"

    def test_analyze_model_foreign_key(self, analyzer):
        """Test analyzing model with foreign key"""

        @dataclass
        class Post(DomainModel):
            id: int
            user_id: int = Field(json_schema_extra={"foreign_key": "users.id"})
            title: str

        table_def = analyzer.analyze_model(Post)

        user_id_col = next(col for col in table_def.columns if col.name == "user_id")
        assert user_id_col.foreign_key == "users.id"

    def test_analyze_model_list_relationship(self, analyzer):
        """Test analyzing model with list relationship"""

        @dataclass
        class Comment(DomainModel):
            id: int
            post_id: int
            content: str

        @dataclass
        class Post(DomainModel):
            id: int
            title: str
            comments: list[Comment]  # This should be handled as relationship

        table_def = analyzer.analyze_model(Post)

        # comments field should be treated as array or ignored for now
        # (full relationship handling would be more complex)
        comments_col = next(
            (col for col in table_def.columns if col.name == "comments"), None,
        )
        if comments_col:
            # Depending on implementation, might be INTEGER[] or ignored
            pass

    def test_analyze_non_domain_model(self, analyzer):
        """Test analyzing non-DomainModel class raises error."""

        class NotADomainModel:
            id: int
            name: str

        with pytest.raises(MigrationError, match="must inherit from DomainModel"):
            analyzer.analyze_model(NotADomainModel)

    def test_camel_to_snake_conversion(self, analyzer):
        """Test camelCase to snake_case conversion"""

        @dataclass
        class UserProfile(DomainModel):
            userId: int
            fullName: str
            isActive: bool

        table_def = analyzer.analyze_model(UserProfile)
        assert table_def.name == "user_profile"

        column_names = list(map(lambda col: col.name, table_def.columns))
        assert "user_id" in column_names
        assert "full_name" in column_names
        assert "is_active" in column_names

    def test_type_mapping(self, analyzer):
        """Test type mapping functionality"""

        # Test direct mappings
        assert analyzer._get_sql_type(str) == "VARCHAR"
        assert analyzer._get_sql_type(int) == "INTEGER"
        assert analyzer._get_sql_type(float) == "FLOAT"
        assert analyzer._get_sql_type(bool) == "BOOLEAN"
        assert analyzer._get_sql_type(datetime) == "TIMESTAMP"
        assert analyzer._get_sql_type(bytes) == "BYTEA"

        # Test string forward reference
        assert analyzer._get_sql_type("SomeClass") == "VARCHAR"

        # Test unknown type defaults to VARCHAR
        class UnknownType:
            pass

        assert analyzer._get_sql_type(UnknownType) == "VARCHAR"

    def test_format_default_value(self, analyzer):
        """Test default value formatting"""

        assert analyzer._format_default_value("test") == "'test'"
        assert analyzer._format_default_value(42) == "42"
        assert analyzer._format_default_value(3.14) == "3.14"
        assert analyzer._format_default_value(True) == "TRUE"
        assert analyzer._format_default_value(False) == "FALSE"
        assert analyzer._format_default_value(None) == "NULL"
        assert analyzer._format_default_value([1, 2, 3]) == "[1, 2, 3]"

    def test_optional_type_detection(self, analyzer):
        """Test optional type detection"""

        # Test Optional[T] detection
        optional_str = str | None
        assert analyzer._is_optional_type(optional_str)
        assert analyzer._get_optional_inner_type(optional_str) is str

        # Test Union with None
        union_str = str | None
        assert analyzer._is_optional_type(union_str)
        assert analyzer._get_optional_inner_type(union_str) is str

        # Test non-optional
        assert not analyzer._is_optional_type(str)

    def test_list_type_detection(self, analyzer):
        """Test list type detection"""

        # Test List[T] detection
        list_str = list[str]
        assert analyzer._is_list_type(list_str)
        assert analyzer._get_list_inner_type(list_str) is str

        # Test non-list
        assert not analyzer._is_list_type(str)

    def test_add_indexes_and_constraints(self, analyzer):
        """Test adding indexes and constraints from Meta"""

        @dataclass
        class User(DomainModel):
            id: int
            email: str
            name: str

            class Meta:
                indexes = [
                    {"name": "ix_users_email", "columns": ["email"]},
                    {"name": "ix_users_name", "columns": ["name"], "unique": True},
                ]
                constraints = [
                    {
                        "name": "ck_email_format",
                        "type": "check",
                        "expression": "email LIKE '%@%'",
                    },
                ]

        table_def = analyzer.analyze_model(User)

        assert len(table_def.indexes) == 2
        assert len(table_def.constraints) == 1

        # Check index details
        email_index = next(
            idx for idx in table_def.indexes if idx["name"] == "ix_users_email"
        )
        assert email_index["columns"] == ["email"]
        assert email_index.get("unique", False) is False

        name_index = next(
            idx for idx in table_def.indexes if idx["name"] == "ix_users_name"
        )
        assert name_index["columns"] == ["name"]
        assert name_index.get("unique", False) is True


