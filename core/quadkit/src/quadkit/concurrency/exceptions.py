"""Exceptions for the concurrency subsystem."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import QuadkitError


class ConcurrencyError(QuadkitError):
    """Base exception for all concurrency errors."""

    _code = "QK_ERR_CONC_001"

    def __init__(self, message: str = "Concurrency error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class AsyncError(ConcurrencyError):
    """Exception raised for errors in asynchronous operations or concurrency control."""

    _code = "QK_ERR_CONC_002"

    def __init__(
        self,
        message: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message or "Async error occurred", **kwargs)


class ChannelClosedError(ConcurrencyError):
    """Raised when an operation is attempted on a closed channel."""

    _code = "QK_ERR_CONC_003"

    def __init__(self, message: str = "Channel is closed", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class ChannelFullError(ConcurrencyError):
    """Raised when sending to a channel that is at capacity."""

    _code = "QK_ERR_CONC_004"

    def __init__(
        self,
        message: str = "Channel is full",
        *,
        capacity: int | None = None,
        **kwargs: Any,
    ) -> None:
        if capacity is not None:
            kwargs.setdefault("details", {})["capacity"] = capacity
        super().__init__(message, **kwargs)
        self.capacity = capacity


class DispatcherError(ConcurrencyError):
    """Error in dispatcher execution."""

    _code = "QK_ERR_CONC_005"

    def __init__(self, message: str = "Dispatcher error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class StructuredParallelismError(ConcurrencyError):
    """Base exception for parallel execution errors."""

    _code = "QK_ERR_CONC_006"

    def __init__(
        self,
        message: str = "Structured parallelism error",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)


class TaskGroupError(StructuredParallelismError):
    """Raised when a task group encounters an error."""

    _code = "QK_ERR_CONC_007"

    def __init__(self, message: str = "Task group error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CancellationScopeError(StructuredParallelismError):
    """Raised when a cancellation scope encounters an error."""

    _code = "QK_ERR_CONC_008"

    def __init__(
        self, message: str = "Cancellation scope error", **kwargs: Any
    ) -> None:
        super().__init__(message, **kwargs)


__all__ = [
    "AsyncError",
    "CancellationScopeError",
    "ChannelClosedError",
    "ChannelFullError",
    "ConcurrencyError",
    "DispatcherError",
    "StructuredParallelismError",
    "TaskGroupError",
]
