"""
Query logger implementations for community edition.

Provides basic query logging functionality including console, file, and memory loggers.
"""

from __future__ import annotations

from collections import deque
from datetime import timedelta
import logging
from logging import FileHandler, Formatter, StreamHandler
import random
from typing import Any

# QueryLogEntry and QueryLoggerProtocol come from contracts
from quadkit.contracts.data.sql.query_log import QueryLogEntry, QueryLoggerProtocol
from quadkit.logging import (
    INFO,
    get_logger,
)
from quadkit.primitives import clock as ambient_clock
from quadkit.serialization import dumps

logger = get_logger(__name__)

LOG_LEVELS = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}


class QueryLoggerBase(QueryLoggerProtocol):
    """Base query logger with common functionality."""

    def __init__(
        self,
        slow_query_threshold: float = 1.0,
        max_entries: int = 1000,
        sample_rate: float = 1.0,
    ):
        """Initialise the query logger.

        Args:
            slow_query_threshold: Queries exceeding this duration in seconds
                are always logged as warnings, regardless of *sample_rate*.
            max_entries: Maximum number of log entries to keep in memory.
            sample_rate: Fraction of normal (non-slow, non-error) queries to
                log, in the range ``(0.0, 1.0]``.  Use ``1.0`` (default) to
                log all queries.  Set to e.g. ``0.1`` to log only 10 %% of
                queries in high-QPS production deployments.  Slow queries and
                error queries are **always** logged regardless of this setting.
        """
        if not 0.0 < sample_rate <= 1.0:
            raise ValueError(f"sample_rate must be in (0.0, 1.0], got {sample_rate!r}")
        self.slow_query_threshold = slow_query_threshold
        self.max_entries = max_entries
        self.sample_rate = sample_rate
        self._entries: deque[QueryLogEntry] = deque(maxlen=max_entries)

        # Structlog compatibility: use bind if available, else standard getChild
        if hasattr(logger, "bind"):
            self.logger = logger.bind(component=self.__class__.__name__)
        elif hasattr(logger, "getChild"):
            self.logger = logger.getChild(self.__class__.__name__)
        else:
            self.logger = logger

    def _should_log(self, entry: QueryLogEntry) -> bool:
        """Return whether *entry* should be logged given the current sample rate.

        Slow queries and error queries are always included.  Normal queries are
        subject to the ``sample_rate`` filter.

        Args:
            entry: The query log entry to test.

        Returns:
            True if the entry should be logged, False if it should be dropped.
        """
        is_slow = entry.execution_time > self.slow_query_threshold
        is_error = not entry.success and bool(entry.error_message)
        if is_slow or is_error:
            return True
        return self.sample_rate >= 1.0 or random.random() <= self.sample_rate  # noqa: S311 — sampling (non-crypto)

    async def log_query(self, entry: QueryLogEntry) -> None:
        """Log a query execution, honouring the configured sample rate.

        Slow queries (exceeding *slow_query_threshold*) and failed queries are
        always recorded regardless of *sample_rate*.  Normal successful queries
        are subject to sampling when ``sample_rate < 1.0``.

        Subclasses should override :meth:`_on_log` to add backend-specific
        output (e.g. to console or a file) rather than overriding this method,
        so that the sampling decision is computed exactly once per entry.

        Args:
            entry: The query log entry to record.
        """
        if not self._should_log(entry):
            return

        self._entries.append(entry)

        # Log slow queries
        if entry.execution_time > self.slow_query_threshold:
            self.logger.warning(
                "SLOW QUERY (%.3fs): %s",
                entry.execution_time,
                entry.sql,
            )

        # Log errors
        if not entry.success and entry.error_message:
            self.logger.error(
                "QUERY ERROR (%.3fs): %s - %s",
                entry.execution_time,
                entry.error_message,
                entry.sql,
            )

        await self._on_log(entry)

    async def _on_log(self, entry: QueryLogEntry) -> None:
        """Backend-specific logging hook called after the entry has been recorded.

        Override this in subclasses to emit the entry to a specific output
        (console, file, etc.).  This method is only called when the entry
        passes the sampling filter, so subclasses do not need to re-check
        *sample_rate*.

        Args:
            entry: The query log entry that was recorded.
        """
        # Default implementation is a no-op; subclasses provide output.

    async def get_recent_queries(self, limit: int = 100) -> list[QueryLogEntry]:
        """Get recent query logs."""
        return list(self._entries)[-limit:]

    async def get_slow_queries(
        self,
        threshold_seconds: float,
        limit: int = 50,
    ) -> list[QueryLogEntry]:
        """Get slow query logs."""
        slow_queries = list(
            filter(
                lambda entry: entry.execution_time > threshold_seconds,
                self._entries,
            ),
        )
        return sorted(slow_queries, key=lambda x: x.execution_time, reverse=True)[
            :limit
        ]

    async def get_query_stats(self, time_range_seconds: int = 3600) -> dict[str, Any]:
        """Get query statistics."""
        now = ambient_clock.now()
        cutoff_time = now - timedelta(seconds=time_range_seconds)

        # Convert to timestamp for comparison
        cutoff_timestamp = cutoff_time.timestamp()

        recent_entries = list(
            filter(
                lambda entry: entry.timestamp.timestamp() > cutoff_timestamp,
                self._entries,
            ),
        )

        if not recent_entries:
            return {
                "total_queries": 0,
                "successful_queries": 0,
                "failed_queries": 0,
                "average_execution_time": 0.0,
                "slow_queries_count": 0,
                "time_range_seconds": time_range_seconds,
            }

        total_queries = len(recent_entries)
        successful_queries = sum(1 for entry in recent_entries if entry.success)
        failed_queries = total_queries - successful_queries

        execution_times = [entry.execution_time for entry in recent_entries]
        average_execution_time = sum(execution_times) / len(execution_times)

        slow_queries_count = sum(
            1
            for entry in recent_entries
            if entry.execution_time > self.slow_query_threshold
        )

        return {
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "average_execution_time": average_execution_time,
            "slow_queries_count": slow_queries_count,
            "time_range_seconds": time_range_seconds,
            "success_rate": (
                successful_queries / total_queries if total_queries > 0 else 0
            ),
        }


class ConsoleQueryLogger(QueryLoggerBase):
    """Query logger that outputs to console.

    Useful for development and debugging.
    """

    def __init__(
        self,
        slow_query_threshold: float = 1.0,
        max_entries: int = 1000,
        log_level: str = "INFO",
        sample_rate: float = 1.0,
    ):
        super().__init__(slow_query_threshold, max_entries, sample_rate=sample_rate)

        # Set up console logging
        # Structlog compatibility: use bind for context, rely on global config for output
        if hasattr(get_logger(), "bind"):
            self.console_logger = get_logger().bind(
                logger_name=f"{self.__class__.__name__}.console",
            )
        else:
            self.console_logger = get_logger(f"{self.__class__.__name__}.console")

        # Only attempt to modify handlers/levels if the logger supports it (standard logging)
        if hasattr(self.console_logger, "setLevel"):
            self.console_logger.setLevel(LOG_LEVELS.get(log_level.upper(), INFO))

        if (
            hasattr(self.console_logger, "handlers")
            and not self.console_logger.handlers
        ):
            handler = StreamHandler()
            formatter = Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            )
            handler.setFormatter(formatter)
            self.console_logger.addHandler(handler)

    async def _on_log(self, entry: QueryLogEntry) -> None:
        """Emit the query entry to the console logger.

        Args:
            entry: The query log entry to emit.
        """
        # Format query for logging
        params_str = f" with params {entry.params}" if entry.params else ""
        status = "SUCCESS" if entry.success else "FAILED"

        message = (
            f"Query {status} ({entry.execution_time:.3f}s): {entry.sql}{params_str}"
        )

        if entry.success:
            self.console_logger.info(message)
        else:
            # Use f-string to ensure the final rendered message contains the details
            # (some logging handlers/formatters may defer formatting of parameterized
            # messages which broke tests expecting the rendered message).
            self.console_logger.error("%s - Error: %s", message, entry.error_message)


class FileQueryLogger(QueryLoggerBase):
    """Query logger that writes to a file.

    Useful for production logging and analysis.
    """

    def __init__(
        self,
        log_file: str,
        slow_query_threshold: float = 1.0,
        max_entries: int = 10000,
        sample_rate: float = 1.0,
        **_kwargs: Any,
    ):
        super().__init__(slow_query_threshold, max_entries, sample_rate=sample_rate)
        self.log_file = log_file

        # Set up file logging
        logger_name = f"{self.__class__.__name__}.file"

        # Use standard logging for explicit file handling if needed, or bind if structlog
        # File logging is tricky with structlog if we want a separate file just for this logger.
        # Ideally, we should use a standard logger for specific file outputs distinct from the main log.

        self.file_logger = logging.getLogger(logger_name)
        self.file_logger.setLevel("INFO")

        if not any(
            isinstance(h, FileHandler) and getattr(h, "baseFilename", None) == log_file
            for h in self.file_logger.handlers
        ):
            handler = FileHandler(log_file)
            formatter = Formatter("%(asctime)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            self.file_logger.addHandler(handler)

    async def _on_log(self, entry: QueryLogEntry) -> None:
        """Emit the query entry to the log file in JSON format.

        Args:
            entry: The query log entry to emit.
        """
        # Format as JSON for structured logging
        log_data = {
            "timestamp": entry.timestamp,
            "sql": entry.sql,
            "params": entry.params,
            "execution_time": entry.execution_time,
            "success": entry.success,
            "error_message": entry.error_message,
            "connection_id": entry.connection_id,
            "transaction_id": entry.transaction_id,
            "user_id": entry.user_id,
            "request_id": entry.request_id,
            "trace_id": entry.trace_id,
        }

        message = dumps(log_data, default=str)
        self.file_logger.info(message)


class MemoryQueryLogger(QueryLoggerBase):
    """Query logger that stores entries in memory.

    Useful for testing and development.
    """

    def __init__(
        self,
        slow_query_threshold: float = 1.0,
        max_entries: int = 1000,
        sample_rate: float = 1.0,
    ):
        super().__init__(slow_query_threshold, max_entries, sample_rate=sample_rate)

    async def log_query(self, entry: QueryLogEntry) -> None:
        """Log a query execution to memory."""
        await super().log_query(entry)
        # Additional memory-specific logic could go here

    async def clear_logs(self) -> None:
        """Clear all logged entries."""
        self._entries.clear()

    async def get_entries_by_sql(self, sql_pattern: str) -> list[QueryLogEntry]:
        """Get entries matching SQL pattern."""
        return list(
            filter(
                lambda entry: sql_pattern.lower() in entry.sql.lower(),
                self._entries,
            ),
        )

    async def get_failed_queries(self) -> list[QueryLogEntry]:
        """Get all failed query entries."""
        return list(filter(lambda entry: not entry.success, self._entries))


__all__ = [
    "ConsoleQueryLogger",
    "FileQueryLogger",
    "MemoryQueryLogger",
    "QueryLoggerBase",
]
