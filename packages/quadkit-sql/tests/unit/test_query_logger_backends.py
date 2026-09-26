"""Console, file, and memory query-logger backend tests."""

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




class TestConsoleQueryLogger:
    """Test ConsoleQueryLogger class"""

    def test_console_query_logger_init(self):
        """Test ConsoleQueryLogger initialization"""
        logger = ConsoleQueryLogger(
            slow_query_threshold=2.0,
            max_entries=500,
            log_level="DEBUG",
        )

        assert logger.slow_query_threshold == 2.0
        assert logger.max_entries == 500
        assert hasattr(logger, "console_logger")

    @pytest.mark.asyncio
    async def test_log_query_success_console(self):
        """Test logging successful query to console"""
        logger = ConsoleQueryLogger()

        entry = QueryLogEntry(
            sql="SELECT * FROM users",
            params=["param1"],
            execution_time=0.5,
            success=True,
            timestamp=datetime.now(),
            error_message=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        assert logger.console_logger is not None
        await logger.log_query(entry)

    @pytest.mark.asyncio
    async def test_log_query_error_console(self):
        """Test logging failed query to console"""
        logger = ConsoleQueryLogger()

        entry = QueryLogEntry(
            sql="SELECT * FROM invalid",
            execution_time=0.1,
            success=False,
            error_message="Table not found",
            timestamp=datetime.now(),
            params=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        assert logger.console_logger is not None
        await logger.log_query(entry)


class TestFileQueryLogger:
    """Test FileQueryLogger class"""

    def test_file_query_logger_init(self):
        """Test FileQueryLogger initialization"""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            logger = FileQueryLogger(
                log_file=temp_file.name,
                slow_query_threshold=2.0,
                max_entries=500,
            )

            assert logger.log_file == temp_file.name
            assert logger.slow_query_threshold == 2.0
            assert logger.max_entries == 500
            assert hasattr(logger, "file_logger")

    @pytest.mark.asyncio
    async def test_log_query_file(self):
        """Test logging query to file"""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            logger = FileQueryLogger(log_file=temp_file.name)

            entry = QueryLogEntry(
                sql="SELECT * FROM users",
                params=["param1"],
                execution_time=0.5,
                success=True,
                connection_id="conn_123",
                timestamp=datetime.now(),
                error_message=None,
                transaction_id=None,
                user_id=None,
            )

            with patch.object(logger.file_logger, "info") as mock_info:
                await logger.log_query(entry)

                mock_info.assert_called_once()
                logged_data = json.loads(mock_info.call_args[0][0])

                assert logged_data["sql"] == "SELECT * FROM users"
                assert logged_data["params"] == ["param1"]
                assert logged_data["execution_time"] == 0.5
                assert logged_data["success"] is True
                assert logged_data["connection_id"] == "conn_123"


class TestMemoryQueryLogger:
    """Test MemoryQueryLogger class"""

    def test_memory_query_logger_init(self):
        """Test MemoryQueryLogger initialization"""
        logger = MemoryQueryLogger(slow_query_threshold=2.0, max_entries=500)

        assert logger.slow_query_threshold == 2.0
        assert logger.max_entries == 500

    @pytest.mark.asyncio
    async def test_clear_logs(self):
        """Test clearing logs"""
        logger = MemoryQueryLogger()

        # Add some entries
        entries = [
            QueryLogEntry(
                sql="Q1",
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
                sql="Q2",
                execution_time=0.2,
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

        assert len(logger._entries) == 2

        await logger.clear_logs()
        assert len(logger._entries) == 0

    @pytest.mark.asyncio
    async def test_get_entries_by_sql(self):
        """Test getting entries by SQL pattern"""
        logger = MemoryQueryLogger()

        entries = [
            QueryLogEntry(
                sql="SELECT * FROM users",
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
                sql="INSERT INTO users",
                execution_time=0.2,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="SELECT * FROM posts",
                execution_time=0.3,
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

        # Search for SELECT queries
        select_entries = await logger.get_entries_by_sql("SELECT")
        assert len(select_entries) == 2
        assert all("SELECT" in entry.sql for entry in select_entries)

        # Search for users table
        user_entries = await logger.get_entries_by_sql("users")
        assert len(user_entries) == 2

    @pytest.mark.asyncio
    async def test_get_failed_queries(self):
        """Test getting failed queries"""
        logger = MemoryQueryLogger()

        entries = [
            QueryLogEntry(
                sql="SELECT 1",
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
                sql="INVALID QUERY",
                execution_time=0.2,
                success=False,
                error_message="Syntax error",
                timestamp=datetime.now(),
                params=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="SELECT 2",
                execution_time=0.3,
                success=True,
                timestamp=datetime.now(),
                params=None,
                error_message=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
            QueryLogEntry(
                sql="BROKEN QUERY",
                execution_time=0.1,
                success=False,
                error_message="Table not found",
                timestamp=datetime.now(),
                params=None,
                connection_id=None,
                transaction_id=None,
                user_id=None,
            ),
        ]

        for entry in entries:
            await logger.log_query(entry)

        failed_queries = await logger.get_failed_queries()
        assert len(failed_queries) == 2
        assert all(not entry.success for entry in failed_queries)
        failed_sql = [entry.sql for entry in failed_queries]
        assert "INVALID QUERY" in failed_sql
        assert "BROKEN QUERY" in failed_sql


