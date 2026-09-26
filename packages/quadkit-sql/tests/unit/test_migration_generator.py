"""MigrationGenerator output tests."""

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




class TestMigrationGenerator:
    """Test MigrationGenerator functionality"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def generator(self, temp_dir):
        """Create migration generator"""
        return MigrationGenerator(temp_dir)

    def test_generator_creation(self, generator):
        """Test generator can be created"""
        assert isinstance(generator, MigrationGenerator)
        assert isinstance(generator.analyzer, ModelAnalyzer)

    def test_generate_migration_from_models(self, generator, temp_dir):
        """Test generating migration from domain entities"""

        @dataclass
        class User(DomainModel):
            id: int
            name: str
            email: str

        @dataclass
        class Post(DomainModel):
            id: int
            title: str
            user_id: int

        migration_file = generator.generate_migration_from_models(
            [User, Post], message="Create users and posts tables",
        )

        # Check that file was created
        assert Path(migration_file).exists()

        # Check file content
        content = Path(migration_file).read_text()
        assert "Create users and posts tables" in content
        assert "create_table('user'" in content
        assert "create_table('post'" in content
        assert "op.create_table" in content

    def test_generate_migration_content(self, generator):
        """Test generating migration content"""

        # Create test schema diff
        user_columns = [
            ColumnDefinition(
                name="id", type_sql="INTEGER", primary_key=True, nullable=False,
            ),
            ColumnDefinition(name="name", type_sql="VARCHAR", nullable=False),
        ]
        user_table = TableDefinition(name="users", columns=user_columns)

        schema_diff = SchemaDiff(
            tables_to_create=[user_table],
            tables_to_drop=[],
            columns_to_add={},
            columns_to_drop={},
            columns_to_modify={},
            indexes_to_add={},
            indexes_to_drop={},
            constraints_to_add={},
            constraints_to_drop={},
        )

        content = generator._generate_migration_content(
            schema_diff, "Test migration", "test_rev",
        )

        assert "Test migration" in content
        assert 'revision: str = "test_rev"' in content
        assert "create_table('users'" in content
        assert "def upgrade() -> None:" in content
        assert "def downgrade() -> None:" in content

    def test_generate_create_table_sql(self, generator):
        """Test generating CREATE TABLE SQL"""

        columns = [
            ColumnDefinition(
                name="id", type_sql="INTEGER", primary_key=True, nullable=False,
            ),
            ColumnDefinition(
                name="name", type_sql="VARCHAR", nullable=False, default="'Anonymous'",
            ),
            ColumnDefinition(
                name="email", type_sql="VARCHAR", nullable=True, unique=True, index=True,
            ),
            ColumnDefinition(
                name="user_id",
                type_sql="INTEGER",
                foreign_key="users.id",
                comment="Reference to user",
            ),
        ]

        table = TableDefinition(
            name="profiles",
            columns=columns,
            indexes=[{"name": "ix_profiles_name", "columns": ["name"]}],
        )

        sql = generator._generate_create_table_sql(table)

        assert "op.create_table('profiles'" in sql
        assert "sa.Column('id', INTEGER" in sql
        assert "primary_key=True" in sql
        assert "nullable=False" in sql
        assert "default='Anonymous'" in sql
        assert "unique=True" in sql
        assert "sa.ForeignKey('users.id')" in sql
        assert ".comment('Reference to user')" in sql
        assert "sa.Index('ix_profiles_name', 'name')" in sql

    def test_generate_add_column_sql(self, generator):
        """Test generating ADD COLUMN SQL"""

        column = ColumnDefinition(
            name="age", type_sql="INTEGER", nullable=True, default="18",
        )

        sql = generator._generate_add_column_sql("users", column)
        assert "op.add_column('users', sa.Column('age', INTEGER" in sql
        assert "default=18" in sql

    def test_generate_drop_column_sql(self, generator):
        """Test generating DROP COLUMN SQL"""

        column = ColumnDefinition(name="old_field", type_sql="VARCHAR")
        sql = generator._generate_drop_column_sql("users", column)
        assert sql == "op.drop_column('users', 'old_field')"

    def test_generate_create_index_sql(self, generator):
        """Test generating CREATE INDEX SQL"""

        index_def = {"name": "ix_users_email", "columns": ["email"], "unique": True}
        sql = generator._generate_create_index_sql("users", index_def)
        assert (
            "op.create_index('ix_users_email', 'users', ['email'], unique=True)" in sql
        )

        # Test without unique
        index_def = {"name": "ix_users_name", "columns": ["name"]}
        sql = generator._generate_create_index_sql("users", index_def)
        assert "op.create_index('ix_users_name', 'users', ['name'])" in sql

    def test_generate_drop_index_sql(self, generator):
        """Test generating DROP INDEX SQL"""

        index_def = {"name": "ix_users_email", "columns": ["email"]}
        sql = generator._generate_drop_index_sql("users", index_def)
        assert sql == "op.drop_index('ix_users_email')"

    def test_generate_drop_table_sql(self, generator):
        """Test generating DROP TABLE SQL"""

        sql = generator._generate_drop_table_sql("users")
        assert sql == "op.drop_table('users')"

    def test_generate_index_definition(self, generator):
        """Test generating index definition for table args"""

        index_def = {"name": "ix_users_email", "columns": ["email"], "unique": True}
        sql = generator._generate_index_definition("users", index_def)
        assert "sa.Index('ix_users_email', 'email', unique=True)" in sql

    def test_format_migration_template(self, generator):
        """Test formatting migration template"""

        upgrade_ops = [
            "op.create_table('users', sa.Column('id', sa.INTEGER(), primary_key=True))",
        ]
        downgrade_ops = ["op.drop_table('users')"]

        content = generator._format_migration_template(
            "Test migration", "test_rev", upgrade_ops, downgrade_ops,
        )

        assert "Test migration" in content
        assert 'revision: str = "test_rev"' in content
        assert "op.create_table('users'" in content
        assert "op.drop_table('users')" in content
        assert "def upgrade() -> None:" in content
        assert "def downgrade() -> None:" in content

    def test_format_migration_template_empty_ops(self, generator):
        """Test formatting migration template with empty operations"""

        content = generator._format_migration_template("Empty migration", None, [], [])

        assert "def upgrade() -> None:" in content
        assert "pass" in content
        assert "def downgrade() -> None:" in content

    def test_create_migration_file(self, generator, temp_dir):
        """Test creating migration file"""

        content = "# Test migration content"
        message = "Test migration file"

        migration_file = generator._create_migration_file(content, message)

        assert migration_file.exists()
        assert migration_file.parent.name == "versions"
        assert migration_file.name.endswith(".py")
        assert "test_migration_file" in migration_file.name

        file_content = migration_file.read_text()
        assert file_content == content

    def test_migration_file_timestamp_format(self, generator, temp_dir):
        """Test migration file has proper timestamp format"""

        content = "# Test"
        migration_file = generator._create_migration_file(content, "Test")

        # Filename should start with YYYYMMDD_HHMMSS
        filename = migration_file.name
        # Split on '_' and take first two parts (date and time), then join them back
        parts = filename.split("_")
        timestamp_part = "_".join(parts[:2])  # YYYYMMDD_HHMMSS
        # Should be YYYYMMDD_HHMMSS format (15 digits with underscore)
        assert len(timestamp_part) == 15
        assert timestamp_part.replace("_", "").isdigit()
        # Should contain underscore in filename
        assert "_" in filename

    def test_migration_with_revision(self, generator, temp_dir):
        """Test generating migration with custom revision"""

        @dataclass
        class User(DomainModel):
            id: int
            name: str

        migration_file = generator.generate_migration_from_models(
            [User], message="Test with revision", revision="custom_rev_123",
        )

        content = Path(migration_file).read_text()


# --- pre-existing tests (recovered from former standalone module) ---
def test_camel_to_snake_and_table_name():
    analyzer = ModelAnalyzer()
    assert analyzer._camel_to_snake("TestModelName") == "test_model_name"


def test_format_default_value_and_sql_type():
    analyzer = ModelAnalyzer()
    assert analyzer._format_default_value("x") == "'x'"
    assert analyzer._format_default_value(True) == "TRUE"
    assert analyzer._format_default_value(5) == "5"
    assert analyzer._format_default_value(None) == "NULL"

    assert analyzer._get_sql_type(str) == "VARCHAR"
    assert analyzer._get_sql_type(int) == "INTEGER"


def test_analyze_model_and_column_properties():
    @dataclass
    class User(DomainModel):
        id: int
        name: str = Field(
            ...,
            description="user name",
            json_schema_extra={"unique": True, "index": True},
        )

        class Meta:
            table_name = "users_table"

    analyzer = ModelAnalyzer()
    table_def = analyzer.analyze_model(User)

    assert table_def.name == "users_table"
    assert any(col.name == "id" and col.primary_key for col in table_def.columns)
    name_col = next(c for c in table_def.columns if c.name == "name")
    assert name_col.unique is True
    assert name_col.index is True
    assert name_col.comment == "user name"


def test_generate_migration_file(tmp_path: Path):
    @dataclass
    class Item(DomainModel):
        id: int
        title: str = Field(..., json_schema_extra={"index": True})

    mg = MigrationGenerator(str(tmp_path))
    path = mg.generate_migration_from_models(
        [Item], message="Create Items", revision="rev1",
    )

    assert Path(path).exists()
    content = Path(path).read_text()
    assert "op.create_table" in content
    # title column should appear in the table definition
    assert "'title'" in content

    # cleanup created file and directory
    versions_dir = tmp_path / "versions"
    for f in versions_dir.iterdir():
        f.unlink()
    versions_dir.rmdir()