from dataclasses import dataclass
from quadkit.validation import Field
from quadkit.domain import DomainModel

from quadkit.sql.migrations.generator import (
    ColumnDefinition,
    MigrationGenerator,
    ModelAnalyzer,
    TableDefinition,
)


def test_analyze_field_with_list_of_models_creates_foreign_key():
    @dataclass
    class Related(DomainModel):
        id: int

        class Meta:
            table_name = "related"

    @dataclass
    class Parent(DomainModel):
        relateds: list[Related] = Field(
            default_factory=list, json_schema_extra={"foreign_key": "related.id"},
        )

    analyzer = ModelAnalyzer()

    table_def = analyzer.analyze_model(Parent)
    # There should be a column for relateds with a foreign key pointing to related.id
    col = next(c for c in table_def.columns if c.name == "relateds")
    assert col.foreign_key == "related.id"
    assert col.type_sql == "INTEGER"


def test_generate_create_table_sql_includes_constraints_and_comments():
    cols = [
        ColumnDefinition(
            name="id",
            type_sql="INTEGER",
            nullable=False,
            primary_key=True,
        ),
        ColumnDefinition(
            name="name",
            type_sql="VARCHAR",
            nullable=False,
            default="'x'",
            unique=True,
            comment="User name",
        ),
        ColumnDefinition(
            name="other_id",
            type_sql="INTEGER",
            foreign_key="others.id",
        ),
    ]
    table = TableDefinition(
        name="users", columns=cols, indexes=[{"columns": ["name"], "unique": True}],
    )

    mg = MigrationGenerator("/tmp")

    create_sql = mg._generate_create_table_sql(table)

    # Basic checks for presence of column definitions
    assert "op.create_table('users'" in create_sql
    assert "sa.Column('id', INTEGER" in create_sql
    assert "primary_key=True" in create_sql
    assert ".comment('User name')" in create_sql
    # Foreign key present
    assert "sa.ForeignKey('others.id')" in create_sql
    # Index definition included
    assert "sa.Index" in create_sql or "op.create_index" in create_sql


def test_index_generation_unique_and_non_unique():
    mg = MigrationGenerator("/tmp")
    idx = {"columns": ["a", "b"]}
    created = mg._generate_create_index_sql("t", idx)
    assert "op.create_index" in created

    idx_unique = {"columns": ["a"], "unique": True}
    created_u = mg._generate_create_index_sql("t", idx_unique)
    assert "unique=True" in created_u

    # Test index definition formatting
    idx_def = mg._generate_index_definition("t", {"columns": ["a", "b"], "name": "ix1"})
    assert "sa.Index('ix1'" in idx_def