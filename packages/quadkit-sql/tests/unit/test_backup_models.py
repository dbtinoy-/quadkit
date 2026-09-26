"""BackupMetadata and TableData model tests."""

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



class TestBackupMetadata:
    """Test BackupMetadata dataclass"""

    def test_backup_metadata_creation(self):
        """Test creating backup metadata"""
        created_at = datetime.now(UTC)
        metadata = BackupMetadata(
            database_type="sql",
            tables=["users", "orders"],
            record_counts={"users": 100, "orders": 50},
            created_at=created_at,
            version="1.0",
            compressed=True,
            checksum="abc123",
        )

        assert metadata.database_type == "sql"
        assert metadata.tables == ["users", "orders"]
        assert metadata.record_counts == {"users": 100, "orders": 50}
        assert metadata.created_at == created_at
        assert metadata.version == "1.0"
        assert metadata.compressed is True
        assert metadata.checksum == "abc123"


class TestTableData:
    """Test TableData dataclass"""

    def test_table_data_creation(self):
        """Test creating table data"""
        data = TableData(
            name="users",
            columns=["id", "name", "email"],
            rows=[[1, "John", "john@example.com"], [2, "Jane", "jane@example.com"]],
            primary_key="id",
        )

        assert data.name == "users"
        assert data.columns == ["id", "name", "email"]
        assert len(data.rows) == 2
        assert data.primary_key == "id"


