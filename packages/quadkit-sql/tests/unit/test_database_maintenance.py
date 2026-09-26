"""Database maintenance task tests."""

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



class TestDatabaseMaintenance:
    """Test DatabaseMaintenance functionality"""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool"""
        return MockConnectionPoolProtocol()

    @pytest.fixture
    def maintenance(self, mock_pool):
        """Create database maintenance instance"""
        return DatabaseMaintenance(mock_pool)

    @pytest.mark.asyncio
    async def test_vacuum_all_tables(self, maintenance):
        """Test vacuuming all tables"""
        await maintenance.vacuum()

        conn = maintenance.connection_pool.mock_conn
        assert len(conn.executed_queries) == 1
        assert conn.executed_queries[0][0] == "VACUUM"

    @pytest.mark.asyncio
    async def test_vacuum_specific_table(self, maintenance):
        """Test vacuuming a specific table"""
        await maintenance.vacuum("users")

        conn = maintenance.connection_pool.mock_conn
        assert len(conn.executed_queries) == 1
        assert conn.executed_queries[0][0] == 'VACUUM "users"'

    @pytest.mark.asyncio
    async def test_analyze_all_tables(self, maintenance):
        """Test analyzing all tables"""
        await maintenance.analyze()

        conn = maintenance.connection_pool.mock_conn
        assert len(conn.executed_queries) == 1
        assert conn.executed_queries[0][0] == "ANALYZE TABLE"

    @pytest.mark.asyncio
    async def test_analyze_specific_table(self, maintenance):
        """Test analyzing a specific table"""
        await maintenance.analyze("users")

        conn = maintenance.connection_pool.mock_conn
        assert len(conn.executed_queries) == 1
        assert conn.executed_queries[0][0] == 'ANALYZE TABLE "users"'

    @pytest.mark.asyncio
    async def test_get_table_sizes(self, maintenance):
        """Test getting table sizes"""
        conn = maintenance.connection_pool.mock_conn
        conn.fetch_results = {
            "SELECT table_name, data_length, index_length, "
            "data_length + index_length as total_size FROM information_schema.tables "
            "WHERE table_schema = DATABASE() "
            "ORDER BY total_size DESC": [
                {
                    "table_name": "users",
                    "data_length": 1024,
                    "index_length": 512,
                    "total_size": 1536,
                },
                {
                    "table_name": "orders",
                    "data_length": 2048,
                    "index_length": 1024,
                    "total_size": 3072,
                },
            ],
        }

        sizes = await maintenance.get_table_sizes()

        assert "users" in sizes
        assert "orders" in sizes
        assert sizes["users"]["total_size"] == 1536
        assert sizes["orders"]["total_size"] == 3072

    @pytest.mark.asyncio
    async def test_get_database_stats(self, maintenance):
        """Test getting database statistics"""
        conn = maintenance.connection_pool.mock_conn
        conn.fetch_results = {
            "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema = DATABASE()": {
                "count": 5,
            },
            "SELECT SUM(table_rows) as total_records FROM information_schema.tables WHERE table_schema = DATABASE()": {
                "total_records": 1500,
            },
            "SELECT SUM(data_length + index_length) as total_size, SUM(data_length) as data_size, "
            "SUM(index_length) as index_size FROM information_schema.tables WHERE table_schema = DATABASE()": {
                "total_size": 1048576,
                "data_size": 786432,
                "index_size": 262144,
            },
        }

        stats = await maintenance.get_database_stats()

        assert stats["table_count"] == 5
        assert stats["total_records"] == 1500
        assert stats["database_size"]["total"] == 1048576
        assert stats["database_size"]["data"] == 786432
        assert stats["database_size"]["index"] == 262144
