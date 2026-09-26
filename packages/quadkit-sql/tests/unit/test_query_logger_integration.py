"""Cross-component query-logger integration tests."""

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




class TestQueryLoggerIntegration:
    """Integration tests for query loggers"""

    @pytest.mark.asyncio
    async def test_multiple_loggers_same_entry(self):
        """Test logging the same entry to multiple loggers"""
        base_logger = QueryLoggerBase()
        memory_logger = MemoryQueryLogger()

        entry = QueryLogEntry(
            sql="SELECT * FROM test_table",
            execution_time=1.5,
            success=True,
            timestamp=datetime.now(),
            params=None,
            error_message=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        # Log to both
        await base_logger.log_query(entry)
        await memory_logger.log_query(entry)

        # Both should have the entry
        assert len(base_logger._entries) == 1
        assert len(memory_logger._entries) == 1

        assert base_logger._entries[0] == entry
        assert memory_logger._entries[0] == entry

    @pytest.mark.asyncio
    async def test_query_logger_with_real_timestamps(self):
        """Test query logger with real timestamp handling"""
        logger = MemoryQueryLogger()

        # Create entries with timestamps in the past
        past_time = datetime.now() - timedelta(seconds=2)

        entry1 = QueryLogEntry(
            sql="SELECT 1",
            execution_time=0.1,
            success=True,
            timestamp=past_time,
            params=None,
            error_message=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        entry2 = QueryLogEntry(
            sql="SELECT 2",
            execution_time=0.2,
            success=True,
            timestamp=past_time + timedelta(seconds=1),
            params=None,
            error_message=None,
            connection_id=None,
            transaction_id=None,
            user_id=None,
        )

        await logger.log_query(entry1)
        await logger.log_query(entry2)

        # Test time-based filtering in stats - should include both entries
        recent_stats = await logger.get_query_stats(time_range_seconds=10)
        assert recent_stats["total_queries"] == 2

        # Test with very short time range - should exclude old entries
        old_stats = await logger.get_query_stats(time_range_seconds=0.5)
        assert old_stats["total_queries"] == 0

    @pytest.mark.asyncio
    async def test_query_logger_max_entries_behavior(self):
        """Test behavior when max entries is exceeded"""
        logger = MemoryQueryLogger(max_entries=3)

        # Add more entries than max_entries
        for i in range(5):
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
            await logger.log_query(entry)

        # Should only keep the last 3 entries
        assert len(logger._entries) == 3

        recent = await logger.get_recent_queries()
        assert len(recent) == 3
        assert recent[0].sql == "SELECT 2"
        assert recent[1].sql == "SELECT 3"
        assert recent[2].sql == "SELECT 4"
