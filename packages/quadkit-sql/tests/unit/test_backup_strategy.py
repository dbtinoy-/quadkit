"""SQL backup strategy tests."""

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



class TestSQLBackupStrategy:
    """Test SQL backup strategy"""

    @pytest.fixture
    def mock_conn(self):
        """Create mock connection with test data"""
        conn = MockDatabaseConnection()

        # Mock column information
        conn.fetch_results = {
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? "
            "AND table_schema = DATABASE() ORDER BY ordinal_position": [
                {"column_name": "id"},
                {"column_name": "name"},
                {"column_name": "email"},
            ],
            "SELECT column_name FROM information_schema.key_column_usage WHERE table_name = ? "
            "AND constraint_name = 'PRIMARY'": [{"column_name": "id"}],
            "SELECT * FROM users": [
                {"id": 1, "name": "John", "email": "john@example.com"},
                {"id": 2, "name": "Jane", "email": "jane@example.com"},
            ],
        }

        return conn

    @pytest.fixture
    def strategy(self):
        """Create SQL backup strategy"""
        return SQLBackupStrategy()

    @pytest.mark.asyncio
    async def test_backup_table(self, strategy, mock_conn):
        """Test backing up a single table"""
        # Setup mock data with parameterized queries
        mock_conn.fetch_results = {
            "SELECT column_name FROM information_schema.columns WHERE table_name = ? "
            "AND table_schema = DATABASE() ORDER BY ordinal_position": [
                {"column_name": "id"},
                {"column_name": "name"},
                {"column_name": "email"},
            ],
            "SELECT column_name FROM information_schema.key_column_usage WHERE table_name = ? "
            "AND constraint_name = 'PRIMARY'": [{"column_name": "id"}],
            'SELECT * FROM "users"': [
                {"id": 1, "name": "John", "email": "john@example.com"},
                {"id": 2, "name": "Jane", "email": "jane@example.com"},
            ],
        }

        result = await strategy.backup_table(mock_conn, "users")

        assert result.name == "users"
        assert result.columns == ["id", "name", "email"]
        assert result.primary_key == "id"
        assert len(result.rows) == 2
        assert result.rows[0] == [1, "John", "john@example.com"]

    @pytest.mark.asyncio
    async def test_get_table_list(self, strategy, mock_conn):
        """Test getting table list"""
        mock_conn.fetch_results = {
            "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() "
            "AND table_type = 'BASE TABLE' AND table_name NOT IN ('schema_migrations', 'migrations')": [
                {"table_name": "users"},
                {"table_name": "orders"},
                {"table_name": "products"},
            ],
        }

        tables = await strategy.get_table_list(mock_conn)
        assert tables == ["users", "orders", "products"]

    @pytest.mark.asyncio
    async def test_get_table_info(self, strategy, mock_conn):
        """Test getting table info"""
        mock_conn.fetch_results = {
            'SELECT COUNT(*) as count FROM "users"': {"count": 150},
        }

        info = await strategy.get_table_info(mock_conn, "users")
        assert info == {"record_count": 150, "table_name": "users"}


