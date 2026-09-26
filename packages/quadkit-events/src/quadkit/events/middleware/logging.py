"""Logging middleware for CQRS buses.

Provides structured logging for command/query execution.
"""

from __future__ import annotations

import time
from typing import Any

from quadkit.events.messages.base import Message
from quadkit.events.middleware.base import AbstractMiddleware, NextHandler
from quadkit.logging import ERROR, INFO, Logger, get_logger


class LoggingMiddleware(AbstractMiddleware[Message, Any]):
    """AbstractMiddleware that logs message execution.

    Logs:
    - Message type and details on entry
    - Execution duration
    - Success/failure status
    - Error details on failure

    Example:
        ```python
        logging_middleware = LoggingMiddleware(
            logger=get_logger("cqrs"),
            log_level=logging.INFO,
            include_message_data=True
        )
        bus.use(logging_middleware)
        ```
    """

    def __init__(
        self,
        logger: Logger | None = None,
        log_level: int = INFO,  # type: ignore[assignment]
        error_log_level: int = ERROR,  # type: ignore[assignment]
        include_message_data: bool = False,
        message_data_max_length: int = 200,
    ):
        """Initialize the logging middleware.

        Args:
            logger: Logger instance (default: creates "quadkit.events" logger)
            log_level: Log level for normal execution
            error_log_level: Log level for errors
            include_message_data: Whether to log message data
            message_data_max_length: Max length for message data in logs
        """
        self._logger = logger or get_logger(__name__)
        self._log_level = log_level
        self._error_log_level = error_log_level
        self._include_message_data = include_message_data
        self._message_data_max_length = message_data_max_length

    async def __call__(self, message: Message, next_handler: NextHandler) -> Any:
        """Execute with logging."""
        message_type = type(message).__name__
        message_id = getattr(message, "id", "N/A")

        # Build log context
        context = {
            "message_type": message_type,
            "message_id": str(message_id),
        }

        if self._include_message_data:
            if hasattr(message, "model_dump"):
                data = str(message.model_dump())
            elif hasattr(message, "__dict__"):
                data = str(message.__dict__)
            else:
                data = repr(message)
            if len(data) > self._message_data_max_length:
                data = data[: self._message_data_max_length] + "..."
            context["message_data"] = data

        # Log entry
        self._logger.log(self._log_level, "Processing %s", message_type, extra=context)

        start_time = time.perf_counter()

        try:
            result = await next_handler(message)
            duration = time.perf_counter() - start_time

            # Log success
            self._logger.log(
                self._log_level,
                "Completed %s in %.3fs",
                message_type,
                duration,
                extra={**context, "duration_seconds": duration, "status": "success"},
            )

            return result

        except Exception as e:  # noqa: BLE001 — middleware observation; records duration and re-raises
            duration = time.perf_counter() - start_time
            self._logger.log(
                self._error_log_level,
                "Failed %s after %.3fs: %s",
                message_type,
                duration,
                e,
                extra={
                    **context,
                    "duration_seconds": duration,
                    "status": "error",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
                exc_info=True,
            )

            raise


__all__ = ["LoggingMiddleware"]
