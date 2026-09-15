"""MCP exception hierarchy for the Quadkit framework.

MCP-specific errors that can occur during MCP server operation.
These extend the base QuadkitError for consistent error handling.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions.base import QuadkitError


class MCPError(QuadkitError):
    """Base exception for all MCP errors."""

    _code = "QK_ERR_MCP_001"

    def __init__(self, message: str = "MCP error", **kwargs: Any) -> None:
        super().__init__(
            message=message,
            **kwargs,
        )


class MCPTransportError(MCPError):
    """Transport-level error (connection, I/O).

    Raised when the MCP transport layer encounters errors
    such as connection failures, timeouts, or I/O errors.
    """

    _code = "QK_ERR_MCP_002"

    def __init__(
        self,
        message: str = "MCP transport error",
        *,
        transport_type: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if transport_type:
            details["transport"] = transport_type
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class MCPToolCallError(MCPError):
    """Tool call failed during MCP execution.

    Raised when a tool invocation fails, either due to
    the tool not existing or raising an exception.
    """

    _code = "QK_ERR_MCP_003"

    def __init__(
        self,
        message: str = "MCP tool call failed",
        *,
        tool_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if tool_name:
            details["tool"] = tool_name
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class MCPResourceError(MCPError):
    """Resource read or list failed.

    Raised when a resource operation fails, such as
    when a resource is not found or cannot be read.
    """

    _code = "QK_ERR_MCP_004"

    def __init__(
        self,
        message: str = "MCP resource error",
        *,
        uri: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if uri:
            details["uri"] = uri
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class MCPProtocolError(MCPError):
    """Protocol violation (malformed message, invalid state).

    Raised when an MCP message violates the protocol specification,
    such as missing required fields or invalid JSON-RPC structure.
    """

    _code = "QK_ERR_MCP_005"

    def __init__(
        self,
        message: str = "MCP protocol error",
        *,
        details: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            message=message,
            details=details or {},
            **kwargs,
        )


class MCPMethodNotFoundError(MCPError):
    """Unknown MCP method requested by client.

    Raised when the client requests an MCP method that
    the server does not support.
    """

    _code = "QK_ERR_MCP_006"

    def __init__(
        self,
        message: str = "MCP method not found",
        *,
        method: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if method:
            details["method"] = method
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class MCPPromptError(MCPError):
    """Prompt retrieval or list failed.

    Raised when a prompt operation fails, such as
    when a prompt is not found or arguments are invalid.
    """

    _code = "QK_ERR_MCP_007"

    def __init__(
        self,
        message: str = "MCP prompt error",
        *,
        prompt_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if prompt_name:
            details["prompt"] = prompt_name
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


class MCPInitializationError(MCPError):
    """MCP server initialization failed.

    Raised when the MCP server cannot be initialized,
    usually due to missing required handlers or
    configuration errors.
    """

    _code = "QK_ERR_MCP_008"

    def __init__(
        self,
        message: str = "MCP initialization failed",
        *,
        reason: str | None = None,
        **kwargs: Any,
    ) -> None:
        details = kwargs.pop("details", {})
        if reason:
            details["reason"] = reason
        super().__init__(
            message=message,
            details=details,
            **kwargs,
        )


__all__ = [
    "MCPError",
    "MCPInitializationError",
    "MCPMethodNotFoundError",
    "MCPPromptError",
    "MCPProtocolError",
    "MCPResourceError",
    "MCPToolCallError",
    "MCPTransportError",
]
