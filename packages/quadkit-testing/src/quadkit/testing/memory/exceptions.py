"""Exceptions for the memory subsystem.

Provides CQRS bus exception types and the base ``MemoryBackendError``.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import QuadkitError
from quadkit.contracts.exceptions.events import (
    DuplicateHandlerError as ContractDuplicateHandlerError,
)
from quadkit.contracts.exceptions.events import EventError, HandlerNotFoundError


class MemoryBackendError(QuadkitError):
    """Base exception for all memory backend errors."""

    _code: str = "QK_ERR_TEST_003"


class CommandBusError(EventError):
    """Raised when a command bus operation fails."""

    _code: str = "QK_ERR_TEST_004"

    def __init__(self, message: str = "Command bus error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class CommandHandlerNotFoundError(CommandBusError, HandlerNotFoundError):
    """Raised when no handler is registered for a specific command type."""

    _code: str = "QK_ERR_TEST_005"

    def __init__(self, command_type: str) -> None:
        HandlerNotFoundError.__init__(
            self,
            message=f"No handler registered for command: {command_type}",
            message_type=command_type,
        )
        self.command_type = command_type


class DuplicateHandlerError(CommandBusError, ContractDuplicateHandlerError):
    """Raised when a handler is already registered for a command type."""

    _code: str = "QK_ERR_TEST_006"

    def __init__(self, command_type: str) -> None:
        ContractDuplicateHandlerError.__init__(
            self,
            message=f"Handler already registered for command: {command_type}",
            message_type=command_type,
        )
        self.command_type = command_type


class CommandError(CommandBusError):
    """Wraps a handler exception for Result-based command dispatch."""

    _code: str = "QK_ERR_TEST_007"

    def __init__(self, cause: BaseException) -> None:
        super().__init__(f"Command handler raised: {cause}")
        self.cause: BaseException = cause


class QueryBusError(EventError):
    """Raised when a query bus operation fails."""

    _code: str = "QK_ERR_TEST_008"

    def __init__(self, message: str = "Query bus error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class QueryHandlerNotFoundError(QueryBusError, HandlerNotFoundError):
    """Raised when no handler is registered for a specific query type."""

    _code: str = "QK_ERR_TEST_009"

    def __init__(self, query_type: str) -> None:
        HandlerNotFoundError.__init__(
            self,
            message=f"No handler registered for query: {query_type}",
            message_type=query_type,
        )
        self.query_type = query_type


class QueryDuplicateHandlerError(QueryBusError, ContractDuplicateHandlerError):
    """Raised when a handler is already registered for a query type."""

    _code: str = "QK_ERR_TEST_010"

    def __init__(self, query_type: str) -> None:
        ContractDuplicateHandlerError.__init__(
            self,
            message=f"Handler already registered for query: {query_type}",
            message_type=query_type,
        )
        self.query_type = query_type


__all__ = [
    "CommandBusError",
    "CommandError",
    "CommandHandlerNotFoundError",
    "DuplicateHandlerError",
    "MemoryBackendError",
    "QueryBusError",
    "QueryDuplicateHandlerError",
    "QueryHandlerNotFoundError",
]
