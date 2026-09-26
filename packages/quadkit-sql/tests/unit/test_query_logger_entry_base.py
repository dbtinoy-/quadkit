"""QueryLogEntry model and QueryLoggerBase contract tests."""

"""Comprehensive tests for query logger implementations"""

from datetime import datetime, timedelta
import tempfile
from unittest.mock import patch

import pytest

from quadkit import serialization as json
from quadkit.sql.logging import (
    ConsoleQueryLogger,
    FileQueryLogger,
    MemoryQueryLogger,
    QueryLogEntry,
    QueryLoggerBase,
)

"""Comprehensive tests for query logger implementations"""




class TestQueryLogEntry:
    """Test QueryLogEntry dataclass"""

    def test_query_log_entry_creation(self):
        """Test creating a QueryLogEntry"""
        timestamp = datetime.now()
        entry = QueryLogEntry(
            sql="SELECT * FROM users",
            params=["param1", "param2"],
            execution_time=0.5,
            success=True,
            error_message=None,
            connection_id="conn_123",
            transaction_id="txn_456",
            user_id="user_789",
            request_id="req_123",
            trace_id="trace_456",
            timestamp=timestamp,
        )

        assert entry.sql == "SELECT * FROM users"
        assert entry.params == ["param1", "param2"]
        assert entry.execution_time == 0.5
        assert entry.success is True
        assert entry.error_message is None
        assert entry.connection_id == "conn_123"
        assert entry.transaction_id == "txn_456"
        assert entry.user_id == "user_789"
        assert entry.request_id == "req_123"
        assert entry.trace_id == "trace_456"
        assert entry.timestamp == timestamp

    def test_query_log_entry_defaults(self):
        """Test QueryLogEntry with default values"""
        timestamp = datetime.now()
        entry = QueryLogEntry(
            sql="SELECT 1",
            execution_time=0.1,
            success=True,
            timestamp=timestamp,
            params=None,
            error_message=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
            request_id=None,
            trace_id=None,
        )

        assert entry.params is None
        assert entry.error_message is None
        assert entry.connection_id is None
        assert entry.transaction_id is None
        assert entry.user_id is None
        assert entry.request_id is None
        assert entry.trace_id is None


class TestBaseQueryLogger:
    """Test QueryLoggerBase class"""

    def test_base_query_logger_init(self):
        """Test QueryLoggerBase initialization"""
        logger = QueryLoggerBase(slow_query_threshold=2.0, max_entries=500)

        assert logger.slow_query_threshold == 2.0
        assert logger.max_entries == 500
        assert len(logger._entries) == 0
        assert logger.logger is not None
        assert hasattr(logger.logger, "info")
        assert hasattr(logger.logger, "warning")
        assert hasattr(logger.logger, "error")

    def test_base_query_logger_defaults(self):
        """Test QueryLoggerBase default values"""
        logger = QueryLoggerBase()

        assert logger.slow_query_threshold == 1.0
        assert logger.max_entries == 1000

    @pytest.mark.asyncio
    async def test_log_query_success(self):
        """Test logging a successful query"""
        logger = QueryLoggerBase()

        entry = QueryLogEntry(
            sql="SELECT * FROM users",
            execution_time=0.5,
            success=True,
            timestamp=datetime.now(),
            params=None,
            error_message=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        await logger.log_query(entry)

        assert len(logger._entries) == 1
        assert logger._entries[0] == entry

    @pytest.mark.asyncio
    async def test_log_query_slow(self):
        """Test logging a slow query"""
        logger = QueryLoggerBase(slow_query_threshold=0.1)

        entry = QueryLogEntry(
            sql="SELECT * FROM users",
            execution_time=0.5,
            success=True,
            timestamp=datetime.now(),
            params=None,
            error_message=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        assert logger.logger is not None
        await logger.log_query(entry)

    @pytest.mark.asyncio
    async def test_log_query_error(self):
        """Test logging a failed query"""
        logger = QueryLoggerBase()

        entry = QueryLogEntry(
            sql="SELECT * FROM invalid_table",
            execution_time=0.1,
            success=False,
            error_message="Table does not exist",
            timestamp=datetime.now(),
            params=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        assert logger.logger is not None
        await logger.log_query(entry)

    @pytest.mark.asyncio
    async def test_get_recent_queries(self):
        """Test getting recent queries"""
        logger = QueryLoggerBase(max_entries=5)

        # Add some entries
        entries = []
        for i in range(7):  # More than max_entries
            entry = QueryLogEntry(
                sql=f"SELECT {i}",
                execution_time=0.1,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            )
            entries.append(entry)
            await logger.log_query(entry)

        # Should only keep max_entries
        assert len(logger._entries) == 5

        recent = await logger.get_recent_queries(3)
        assert len(recent) == 3
        assert recent[0].sql == "SELECT 4"
        assert recent[1].sql == "SELECT 5"
        assert recent[2].sql == "SELECT 6"

    @pytest.mark.asyncio
    async def test_get_slow_queries(self):
        """Test getting slow queries"""
        logger = QueryLoggerBase()

        # Add queries with different execution times
        entries = [
            QueryLogEntry(
                sql="FAST",
                execution_time=0.1,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="SLOW1",
                execution_time=2.0,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="SLOW2",
                execution_time=3.0,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="MEDIUM",
                execution_time=1.5,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
        ]

        for entry in entries:
            await logger.log_query(entry)

        slow_queries = await logger.get_slow_queries(1.0, limit=2)

        assert len(slow_queries) == 2
        # Should be sorted by execution time descending
        assert slow_queries[0].sql == "SLOW2"
        assert slow_queries[1].sql == "SLOW1"

    @pytest.mark.asyncio
    async def test_get_query_stats_empty(self):
        """Test getting query stats when no queries logged"""
        logger = QueryLoggerBase()

        stats = await logger.get_query_stats()

        expected_stats = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "average_execution_time": 0.0,
            "slow_queries_count": 0,
            "time_range_seconds": 3600,
        }

        for key, value in expected_stats.items():
            assert stats[key] == value

    @pytest.mark.asyncio
    async def test_get_query_stats_with_data(self):
        """Test getting query stats with logged queries"""
        logger = QueryLoggerBase(slow_query_threshold=1.0)

        # Add some test entries
        entries = [
            QueryLogEntry(
                sql="Q1",
                execution_time=0.5,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="Q2",
                execution_time=2.0,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="Q3",
                execution_time=0.8,
                success=False,
                error_message="Error",
                timestamp=datetime.now(),
                params=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
        ]

        for entry in entries:
            await logger.log_query(entry)

        stats = await logger.get_query_stats(time_range_seconds=3600)

        assert stats["total_queries"] == 3
        assert stats["successful_queries"] == 2
        assert stats["failed_queries"] == 1
        assert stats["average_execution_time"] == (0.5 + 2.0 + 0.8) / 3
        assert stats["slow_queries_count"] == 1  # Only Q2 is slow
        assert stats["success_rate"] == 2 / 3


