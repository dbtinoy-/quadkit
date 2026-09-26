"""
Unit tests for SimpleMigrationManager

Tests migration tracking, application, and file operations.
"""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts import (
    DatabaseProviderProtocol,
    MigrationRecord,
    QueryResult,
)
from quadkit.sql.migrations.manager import SimpleMigrationManager


class TestSimpleMigrationManager:
    """Test SimpleMigrationManager functionality"""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock database provider"""
        provider = MagicMock(spec=DatabaseProviderProtocol)
        provider.table_exists = AsyncMock()
        provider.execute = AsyncMock()
        provider.execute_query = AsyncMock()
        provider.execute_insert = AsyncMock()
        return provider

    @pytest.fixture
    def migration_manager(self, mock_provider, tmp_path):
        """Create a SimpleMigrationManager instance"""
        return SimpleMigrationManager(
            provider=mock_provider, migrations_dir=str(tmp_path / "migrations"),
        )

    @pytest.fixture
    def sample_migration_record(self):
        """Create a sample migration record"""
        return MigrationRecord(
            version="20240101120000",
            name="create_users_table",
            applied_at=datetime.now(UTC),
            success=True,
            error_message=None,
        )

    def test_init_default_migrations_dir(self, mock_provider):
        """Test initialization with default migrations directory"""
        manager = SimpleMigrationManager(mock_provider)
        assert manager.provider == mock_provider
        assert manager.migrations_dir == Path("migrations")
        assert manager.migration_table == "__migrations"

    def test_init_custom_migrations_dir(self, mock_provider, tmp_path):
        """Test initialization with custom migrations directory"""
        custom_dir = tmp_path / "custom_migrations"
        manager = SimpleMigrationManager(mock_provider, str(custom_dir))
        assert manager.migrations_dir == custom_dir

    @pytest.mark.asyncio
    async def test_initialize_migration_table_table_exists(
        self, migration_manager, mock_provider,
    ):
        """Test initialize_migration_table when table already exists"""
        mock_provider.table_exists.return_value = True

        await migration_manager.initialize_migration_table()

        mock_provider.table_exists.assert_called_once_with("__migrations")
        mock_provider.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_migration_table_table_not_exists(
        self, migration_manager, mock_provider,
    ):
        """Test initialize_migration_table when table doesn't exist"""
        mock_provider.table_exists.return_value = False

        await migration_manager.initialize_migration_table()

        mock_provider.table_exists.assert_called_once_with("__migrations")
        mock_provider.execute.assert_called_once()
        assert "CREATE TABLE __migrations" in mock_provider.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_applied_migrations_success(
        self, migration_manager, mock_provider, sample_migration_record,
    ):
        """Test get_applied_migrations with successful query"""
        mock_provider.execute_query.return_value = QueryResult(
            rows=[
                {
                    "version": sample_migration_record.version,
                    "name": sample_migration_record.name,
                    "applied_at": sample_migration_record.applied_at,
                    "success": sample_migration_record.success,
                    "error_message": sample_migration_record.error_message,
                },
            ],
            row_count=1,
            execution_time=0.1,
            success=True,
        )

        migrations = await migration_manager.get_applied_migrations()

        assert len(migrations) == 1
        assert migrations[0].version == sample_migration_record.version
        assert migrations[0].name == sample_migration_record.name
        assert migrations[0].success == sample_migration_record.success

        mock_provider.execute_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_applied_migrations_empty_result(
        self, migration_manager, mock_provider,
    ):
        """Test get_applied_migrations with no migrations"""
        mock_provider.table_exists.return_value = True
        mock_provider.execute_query.return_value = QueryResult(
            rows=[],
            row_count=0,
            execution_time=0.1,
            success=True,
        )

        migrations = await migration_manager.get_applied_migrations()

        assert migrations == []

    @pytest.mark.asyncio
    async def test_apply_migration_success(
        self, migration_manager, mock_provider,
    ):
        """Test apply_migration with successful SQL statement"""
        version = "20240101120000"
        name = "create_users_table"
        sql = "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);"

        success = await migration_manager.apply_migration(version, name, sql)

        assert success is True

        # Verify SQL execution
        # Two calls: 1. the migration SQL, 2. the insertion into __migrations
        assert mock_provider.execute.call_count == 2
        mock_provider.execute.assert_any_call(sql)

    @pytest.mark.asyncio
    async def test_apply_migration_failure_sql_error(
        self, migration_manager, mock_provider,
    ):
        """Test apply_migration when SQL execution fails"""
        version = "20240101120000"
        name = "create_users_table"
        sql = "CREATE TABLE invalid syntax ("

        mock_provider.execute.side_effect = [RuntimeError("Syntax error"), None]

        success = await migration_manager.apply_migration(version, name, sql)

        assert success is False
        assert mock_provider.execute.call_count == 2 # 1 failed migration, 1 recording failure

    @pytest.mark.asyncio
    async def test_rollback_migration(self, migration_manager, mock_provider):
        """Test rollback_migration"""
        version = "20240101120000"
        success = await migration_manager.rollback_migration(version)
        
        assert success is True
        mock_provider.execute.assert_called_once()
        assert 'DELETE FROM "__migrations"' in mock_provider.execute.call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_pending_migrations(
        self, migration_manager, mock_provider, sample_migration_record,
    ):
        """Test get_pending_migrations"""
        # Mock applied migrations
        mock_provider.table_exists.return_value = True
        mock_provider.execute_query.return_value = QueryResult(
            rows=[
                {
                    "version": sample_migration_record.version,
                    "name": sample_migration_record.name,
                    "applied_at": sample_migration_record.applied_at,
                    "success": sample_migration_record.success,
                    "error_message": sample_migration_record.error_message,
                },
            ],
            row_count=1,
            execution_time=0.1,
            success=True,
        )

        available_migrations = ["20240101120000", "20240101130000", "20240101140000"]
        pending = await migration_manager.get_pending_migrations(available_migrations)

        assert pending == ["20240101130000", "20240101140000"]

    @pytest.mark.asyncio
    async def test_apply_pending_migrations_with_files(
        self, migration_manager, mock_provider,
    ):
        """Test apply_pending_migrations with migration files"""
        migration_manager.migrations_dir.mkdir()

        # Create migration files
        (migration_manager.migrations_dir / "20240101120000.sql").write_text(
            "-- Create users table\nCREATE TABLE users (id INTEGER);",
        )
        (migration_manager.migrations_dir / "20240101130000.sql").write_text(
            "-- Create posts table\nCREATE TABLE posts (id INTEGER);",
        )

        # Mock no applied migrations
        mock_provider.table_exists.return_value = True
        mock_provider.execute_query.return_value = QueryResult(
            rows=[],
            row_count=0,
            execution_time=0.1,
            success=True,
        )

        applied = await migration_manager.apply_pending_migrations()

        assert len(applied) == 2
        assert "20240101120000" in applied
        assert "20240101130000" in applied

    @pytest.mark.asyncio
    async def test_create_migration_file(self, migration_manager):
        """Test create_migration_file"""
        name = "add_email_column"
        sql = "ALTER TABLE users ADD COLUMN email TEXT;"

        version = await migration_manager.create_migration_file(name, sql)

        # Verify version format (timestamp)
        assert len(version) == 14  # YYYYMMDDHHMMSS format
        assert version.isdigit()

        # Verify file was created
        migration_file = migration_manager.migrations_dir / f"{version}.sql"
        assert migration_file.exists()

        # Verify file content
        content = migration_file.read_text()
        expected_content = f"-- {name}\n{sql}\n"
        assert content == expected_content
