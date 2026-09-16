"""Event bus and messaging exception classes."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class EventError(QuadkitError):
    """Base events/messaging error."""

    _code = "QK_ERR_EVT_001"

    def __init__(self, message: str = "Events error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class HandlerNotFoundError(EventError):
    """Event/command handler not found.

    Raised when no handler is registered for a specific event or command type.
    """

    _code = "QK_ERR_EVT_002"

    def __init__(
        self,
        message: str = "Handler not found",
        handler_type: str | None = None,
        message_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if handler_type:
            details["handler_type"] = handler_type
        if message_type:
            details["message_type"] = message_type
        kwargs["details"] = details
        super().__init__(message, **kwargs)


__all__ = [
    "DuplicateHandlerError",
    "EventError",
    "HandlerNotFoundError",
]


class DuplicateHandlerError(EventError):
    """Duplicate handler registration.

    Raised when attempting to register a handler for a type that already has one.
    """

    _code = "QK_ERR_EVT_003"

    def __init__(
        self,
        message: str = "Duplicate handler",
        message_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.get("details", {})
        if message_type:
            details["message_type"] = message_type
        kwargs["details"] = details
        super().__init__(message, **kwargs)
