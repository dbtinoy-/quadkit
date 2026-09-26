"""Migration generation from Domain models for Quadkit Framework"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quadkit.domain import DomainModel
from quadkit.primitives import clock as ambient_clock
from quadkit.sql.migrations.base import MigrationError as MigrationError
from quadkit.sql.migrations.model_analyzer import ModelAnalyzer as ModelAnalyzer
from quadkit.sql.types import ColumnDefinition, SchemaDiff, TableDefinition


class MigrationGenerator:
    """Generates Alembic migration files from schema differences"""

    def __init__(self, migrations_path: str | Path) -> None:
        self.migrations_path = Path(migrations_path)
        self.analyzer = ModelAnalyzer()

    def generate_migration_from_models(
        self,
        models: list[type[DomainModel]],
        message: str = "Auto-generated migration",
        revision: str | None = None,
    ) -> str:
        """Generate migration from Domain models"""
        # Analyze all models
        table_definitions = [self.analyzer.analyze_model(m) for m in models]

        # For now, assume all tables need to be created
        # In a full implementation, this would compare with existing schema
        schema_diff = SchemaDiff(
            tables_to_create=table_definitions,
            tables_to_drop=[],
            columns_to_add={},
            columns_to_drop={},
            columns_to_modify={},
            indexes_to_add={},
            indexes_to_drop={},
            constraints_to_add={},
            constraints_to_drop={},
        )

        # Generate migration content
        migration_content = self._generate_migration_content(
            schema_diff,
            message,
            revision,
        )

        # Write migration file
        migration_file = self._create_migration_file(migration_content, message)

        return str(migration_file)

    def _generate_migration_content(
        self,
        schema_diff: SchemaDiff,
        message: str,
        revision: str | None,
    ) -> str:
        """Generate the content of the migration file"""
        # Generate upgrade operations
        upgrade_ops: list[str] = []

        # Create tables
        upgrade_ops.extend(
            self._generate_create_table_sql(table)
            for table in schema_diff.tables_to_create
        )

        # Add columns
        upgrade_ops.extend(
            self._generate_add_column_sql(table_name, column)
            for table_name, columns in schema_diff.columns_to_add.items()
            for column in columns
        )

        # Create indexes
        upgrade_ops.extend(
            self._generate_create_index_sql(table_name, index)
            for table_name, indexes in schema_diff.indexes_to_add.items()
            for index in indexes
        )

        # Generate downgrade operations (reverse of upgrade)
        downgrade_ops: list[str] = []

        # Drop indexes
        downgrade_ops.extend(
            self._generate_drop_index_sql(table_name, index)
            for table_name, indexes in schema_diff.indexes_to_add.items()
            for index in indexes
        )

        # Drop columns
        downgrade_ops.extend(
            self._generate_drop_column_sql(table_name, column)
            for table_name, columns in schema_diff.columns_to_add.items()
            for column in columns
        )

        # Drop tables
        downgrade_ops.extend(
            self._generate_drop_table_sql(table.name)
            for table in reversed(schema_diff.tables_to_create)
        )

        # Format the migration content
        return self._format_migration_template(
            message,
            revision,
            upgrade_ops,
            downgrade_ops,
        )

    def _generate_create_table_sql(self, table: TableDefinition) -> str:
        """Generate CREATE TABLE SQL"""
        columns_sql = []
        for column in table.columns:
            col_sql = f"    sa.Column('{column.name}', {column.type_sql}"

            if not column.nullable:
                col_sql += ", nullable=False"

            if column.default:
                col_sql += f", default={column.default}"

            if column.primary_key:
                col_sql += ", primary_key=True"

            if column.unique:
                col_sql += ", unique=True"

            if column.foreign_key:
                col_sql += f", sa.ForeignKey('{column.foreign_key}')"

            col_sql += ")"

            if column.comment:
                col_sql += f".comment('{column.comment}')"

            columns_sql.append(col_sql)

        columns_str = ",\n".join(columns_sql)

        # Add table-level constraints and indexes
        table_args = []

        # Add indexes
        for index in table.indexes:
            index_sql = self._generate_index_definition(table.name, index)
            table_args.append(index_sql)

        table_args_str = ""
        if table_args:
            table_args_str = ",\n" + ",\n".join(table_args)

        return f"""op.create_table('{table.name}',
{columns_str}{table_args_str}
)"""

    def _generate_add_column_sql(
        self,
        table_name: str,
        column: ColumnDefinition,
    ) -> str:
        """Generate ADD COLUMN SQL"""
        col_sql = f"sa.Column('{column.name}', {column.type_sql}"

        if not column.nullable:
            col_sql += ", nullable=False"

        if column.default:
            col_sql += f", default={column.default}"

        if column.primary_key:
            col_sql += ", primary_key=True"

        if column.unique:
            col_sql += ", unique=True"

        if column.foreign_key:
            col_sql += f", sa.ForeignKey('{column.foreign_key}')"

        col_sql += ")"

        return f"op.add_column('{table_name}', {col_sql})"

    def _generate_drop_column_sql(
        self,
        table_name: str,
        column: ColumnDefinition,
    ) -> str:
        """Generate DROP COLUMN SQL"""
        return f"op.drop_column('{table_name}', '{column.name}')"

    def _generate_create_index_sql(
        self,
        table_name: str,
        index_def: dict[str, Any],
    ) -> str:
        """Generate CREATE INDEX SQL"""
        index_name = index_def.get(
            "name",
            f"ix_{table_name}_{'_'.join(index_def['columns'])}",
        )
        columns = index_def["columns"]
        unique = index_def.get("unique", False)

        if unique:
            return f"op.create_index('{index_name}', '{table_name}', {columns}, unique=True)"
        return f"op.create_index('{index_name}', '{table_name}', {columns})"

    def _generate_drop_index_sql(
        self,
        table_name: str,
        index_def: dict[str, Any],
    ) -> str:
        """Generate DROP INDEX SQL"""
        index_name = index_def.get(
            "name",
            f"ix_{table_name}_{'_'.join(index_def['columns'])}",
        )
        return f"op.drop_index('{index_name}')"

    def _generate_drop_table_sql(self, table_name: str) -> str:
        """Generate DROP TABLE SQL"""
        return f"op.drop_table('{table_name}')"

    def _generate_index_definition(
        self,
        table_name: str,
        index_def: dict[str, Any],
    ) -> str:
        """Generate index definition for table args"""
        index_name = index_def.get(
            "name",
            f"ix_{table_name}_{'_'.join(index_def['columns'])}",
        )
        columns = index_def["columns"]
        unique = index_def.get("unique", False)

        columns_str = ", ".join(f"'{col}'" for col in columns)

        if unique:
            return f"sa.Index('{index_name}', {columns_str}, unique=True)"
        return f"sa.Index('{index_name}', {columns_str})"

    def _format_migration_template(
        self,
        message: str,
        revision: str | None,
        upgrade_ops: list[str],
        downgrade_ops: list[str],
    ) -> str:
        """Format the migration file template"""
        upgrade_str = "\n    ".join(upgrade_ops) if upgrade_ops else "pass"
        downgrade_str = "\n    ".join(downgrade_ops) if downgrade_ops else "pass"

        rev_id = revision or "auto_generated"

        return f'''"""{message}

Revision ID: {{up_revision}}
Revises: {{down_revision}}
Create Date: {{create_date}}

"""
from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "{rev_id}"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade database schema."""
    {upgrade_str}


def downgrade() -> None:
    """Downgrade database schema."""
    {downgrade_str}
'''

    def _create_migration_file(self, content: str, message: str) -> Path:
        """Create the migration file"""
        # Create versions directory if it doesn't exist
        versions_dir = self.migrations_path / "versions"
        versions_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        now = ambient_clock.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S") if now else "000000_000000"
        safe_message = "_".join(message.lower().split())
        filename = f"{timestamp}_{safe_message}.py"

        # Write file
        migration_file = versions_dir / filename
        migration_file.write_text(content)

        return migration_file
