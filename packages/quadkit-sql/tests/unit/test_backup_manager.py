"""BackupManager orchestration tests."""

from __future__ import annotations

"""Tests for Quadkit DB backup functionality"""

from datetime import UTC, datetime
import gzip
import json

import pytest

import os
from quadkit.sql.abstractions.connection import DatabaseConnection
from quadkit.sql.backup.backup_manager import (
    BackupManager,
    BackupMetadata,
    DatabaseMaintenance,
    SQLBackupStrategy,
    TableData,
)



class MockDatabaseConnection(DatabaseConnection):
    """Mock database connection for testing"""

    def __init__(self, mock_data=None):
        self.mock_data = mock_data or {}
        self.executed_queries = []
        self.fetch_results = {}

    async def execute(self, query: str, params=None):
        self.executed_queries.append((query, params))
        return None

    async def execute_many(self, query: str, params_list):
        self.executed_queries.append((query, params_list))
        return None

    async def fetch_one(self, query: str, params=None):
        # Handle parameterized queries by looking up by query pattern
        results = self._get_results_for_query(query, params)
        return results[0] if results else None

    async def fetch_all(self, query: str, params=None):
        # Handle parameterized queries by looking up by query pattern
        return self._get_results_for_query(query, params)

    def _get_results_for_query(self, query: str, params=None):
        """Get mock results for a query, handling parameters"""
        # First try exact match
        if query in self.fetch_results:
            value = self.fetch_results[query]
            if isinstance(value, dict):
                return [value]
            elif isinstance(value, list):
                return value
            else:
                return [value]

        # Try pattern matching for parameterized queries
        for pattern, value in self.fetch_results.items():
            if self._matches_query_pattern(query, pattern):
                if isinstance(value, dict):
                    return [value]
                elif isinstance(value, list):
                    return value
                else:
                    return [value]

        return []

    def _matches_query_pattern(self, query: str, pattern: str) -> bool:
        """Check if query matches a pattern (ignoring parameter placeholders and whitespace)"""

        # Normalize by removing extra whitespace and newlines
        def normalize(q):
            return " ".join(q.split()).replace(" ?", " {}").replace("?", "{}")

        query_normalized = normalize(query)
        pattern_normalized = normalize(pattern)
        return query_normalized == pattern_normalized

    async def close(self):
        pass


class MockConnectionPoolProtocol:
    """Mock connection pool for testing"""

    def __init__(self, mock_conn=None):
        self.mock_conn = mock_conn or MockDatabaseConnection()

    def get_connection(self):
        # Return an async context manager directly
        return MockAsyncContextManager(self.mock_conn)

    async def close(self):
        pass

    async def health_check(self):
        return {"status": "healthy"}

    def get_stats(self):
        return {"connections": 1}


class MockAsyncContextManager:
    """Mock async context manager for database connections"""

    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass



class TestBackupManager:
    """Test BackupManager functionality"""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool"""
        return MockConnectionPoolProtocol()

    @pytest.fixture
    def backup_manager(self, mock_pool):
        """Create backup manager"""
        return BackupManager(mock_pool)

    @pytest.mark.asyncio
    async def test_create_backup_uncompressed(self, backup_manager, tmp_path):
        """Test creating uncompressed backup"""
        # Setup mock data
        conn = backup_manager.connection_pool.mock_conn
        conn.fetch_results = {
            "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() "
            "AND table_type = 'BASE TABLE' AND table_name NOT IN ('schema_migrations', 'migrations')": [
                {"table_name": "users"},
            ],
            'SELECT COUNT(*) as count FROM "users"': {"count": 2},
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? "
            "AND table_schema = DATABASE() ORDER BY ordinal_position": [
                {"column_name": "id"},
                {"column_name": "name"},
            ],
            "SELECT column_name FROM information_schema.key_column_usage WHERE table_name = ? "
            "AND constraint_name = 'PRIMARY'": {"column_name": "id"},
            'SELECT * FROM "users"': [
                {"id": 1, "name": "John"},
                {"id": 2, "name": "Jane"},
            ],
        }

        backup_path = tmp_path / "test_backup"
        metadata = await backup_manager.create_backup(backup_path, compress=False)

        assert metadata.database_type == "sql"
        assert metadata.tables == ["users"]
        assert metadata.record_counts == {"users": 2}
        assert not metadata.compressed

        # Check file was created
        backup_file = tmp_path / "test_backup.json"
        assert backup_file.exists()

        # Verify backup contents
        with open(backup_file) as f:
            data = json.loads(f.read())

        assert "metadata" in data
        assert "tables" in data
        assert len(data["tables"]) == 1
        assert data["tables"][0]["name"] == "users"
        assert len(data["tables"][0]["rows"]) == 2

    @pytest.mark.asyncio
    async def test_create_backup_compressed(self, backup_manager, tmp_path):
        """Test creating compressed backup"""
        # Setup mock data
        conn = backup_manager.connection_pool.mock_conn
        conn.fetch_results = {
            "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() "
            "AND table_type = 'BASE TABLE' AND table_name NOT IN ('schema_migrations', 'migrations')": [
                {"table_name": "users"},
            ],
            'SELECT COUNT(*) as count FROM "users"': {"count": 1},
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? "
            "AND table_schema = DATABASE() ORDER BY ordinal_position": [
                {"column_name": "id"},
                {"column_name": "name"},
            ],
            "SELECT column_name FROM information_schema.key_column_usage WHERE table_name = ? "
            "AND constraint_name = 'PRIMARY'": {"column_name": "id"},
            'SELECT * FROM "users"': [{"id": 1, "name": "John"}],
        }

        backup_path = tmp_path / "test_backup"
        metadata = await backup_manager.create_backup(backup_path, compress=True)

        assert metadata.compressed

        # Check compressed file was created
        backup_file = tmp_path / "test_backup.json.gz"
        assert backup_file.exists()

        # Verify we can read the compressed backup
        with gzip.open(backup_file, "rt") as f:
            data = json.loads(f.read())

        assert "metadata" in data
        assert "tables" in data

    @pytest.mark.asyncio
    async def test_restore_backup(self, backup_manager, tmp_path):
        """Test restoring from backup"""
        # Create test backup data
        backup_data = {
            "metadata": {
                "database_type": "sql",
                "tables": ["users"],
                "record_counts": {"users": 2},
                "created_at": datetime.now(UTC).isoformat(),
                "version": "1.0",
                "compressed": False,
            },
            "tables": [
                {
                    "name": "users",
                    "columns": ["id", "name"],
                    "rows": [[1, "John"], [2, "Jane"]],
                    "primary_key": "id",
                },
            ],
        }

        # Write backup file
        backup_path = tmp_path / "test_backup.json"
        with open(backup_path, "w") as f:
            f.write(json.dumps(backup_data, default=str))

        # Restore backup
        await backup_manager.restore_backup(backup_path)

        # Check that restore operations were executed
        conn = backup_manager.connection_pool.mock_conn
        assert len(conn.executed_queries) > 0

        # Should have DELETE and INSERT queries
        queries = list(map(lambda q: q[0], conn.executed_queries))
        assert any('DELETE FROM "users"' in q for q in queries)
        assert any('INSERT INTO "users"' in q for q in queries)

    @pytest.mark.asyncio
    async def test_list_backups(self, backup_manager, tmp_path):
        """Test listing backups"""
        # Create test backup files
        backup_data = {
            "metadata": {
                "database_type": "sql",
                "tables": ["users"],
                "record_counts": {"users": 10},
                "created_at": "2023-01-01T12:00:00",
                "version": "1.0",
                "compressed": False,
            },
            "tables": [],
        }

        # Create uncompressed backup
        backup1_path = tmp_path / "backup1.json"
        with open(backup1_path, "w") as f:
            f.write(json.dumps(backup_data))

        # Create compressed backup
        backup_data["metadata"]["compressed"] = True
        backup_data["metadata"]["created_at"] = "2023-01-02T12:00:00"
        backup2_path = tmp_path / "backup2.json.gz"
        with gzip.open(backup2_path, "wt") as f:
            f.write(json.dumps(backup_data))

        # List backups
        backups = await backup_manager.list_backups(tmp_path)

        assert len(backups) == 2
        # Should be sorted by creation date (newest first)
        assert backups[0]["filename"] == "backup2.json.gz"
        assert backups[1]["filename"] == "backup1.json"

    @pytest.mark.asyncio
    async def test_validate_backup_valid(self, backup_manager, tmp_path):
        """Test validating a valid backup"""
        backup_data = {
            "metadata": {
                "database_type": "sql",
                "tables": ["users", "orders"],
                "record_counts": {"users": 100, "orders": 50},
                "created_at": datetime.now(UTC).isoformat(),
                "version": "1.0",
                "compressed": False,
            },
            "tables": [
                {
                    "name": "users",
                    "columns": ["id", "name"],
                    "rows": [[1, "John"], [2, "Jane"]],
                    "primary_key": "id",
                },
            ],
        }

        backup_path = tmp_path / "valid_backup.json"
        with open(backup_path, "w") as f:
            f.write(json.dumps(backup_data))

        result = await backup_manager.validate_backup(backup_path)

        assert result["valid"] is True
        assert result["issues"] == []
        assert result["table_count"] == 1
        assert result["total_records"] == 2

    @pytest.mark.asyncio
    async def test_validate_backup_invalid(self, backup_manager, tmp_path):
        """Test validating an invalid backup"""
        # Create invalid backup (missing tables section)
        backup_data = {
            "metadata": {
                "database_type": "sql",
                "created_at": datetime.now(UTC).isoformat(),
            },
        }

        backup_path = tmp_path / "invalid_backup.json"
        with open(backup_path, "w") as f:
            f.write(json.dumps(backup_data))

        result = await backup_manager.validate_backup(backup_path)

        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert "Missing tables section" in result["issues"]


