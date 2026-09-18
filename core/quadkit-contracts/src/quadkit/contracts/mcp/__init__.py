"""MCP protocol contracts for the Quadkit framework.

This package contains the contracts (protocols, types, and errors) for
the Model Context Protocol (MCP) server implementation.

The MCP protocol enables AI agents to interact with Quadkit applications,
exposing tools, resources, and prompts via a standardized interface.
"""

from __future__ import annotations

from quadkit.contracts.mcp.exceptions import (
    MCPError,
    MCPInitializationError,
    MCPMethodNotFoundError,
    MCPPromptError,
    MCPProtocolError,
    MCPResourceError,
    MCPToolCallError,
    MCPTransportError,
)
from quadkit.contracts.mcp.protocols import (
    MCPResourceHandlerProtocol,
    MCPServerProtocol,
    MCPToolHandlerProtocol,
    MCPToolProviderProtocol,
    MCPTransportProtocol,
)

__all__ = [
    "MCPError",
    "MCPInitializationError",
    "MCPMethodNotFoundError",
    "MCPPromptError",
    "MCPProtocolError",
    "MCPResourceError",
    "MCPResourceHandlerProtocol",
    "MCPServerProtocol",
    "MCPToolCallError",
    "MCPToolHandlerProtocol",
    "MCPToolProviderProtocol",
    "MCPTransportError",
    "MCPTransportProtocol",
]
