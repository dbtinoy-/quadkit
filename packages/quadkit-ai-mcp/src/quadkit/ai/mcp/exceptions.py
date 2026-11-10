"""MCP exceptions - re-exported from contracts.

This module re-exports the MCP error hierarchy from quadkit-contracts
for convenient access within the the optional provider package.

Extensions that need to add package-specific exceptions can extend
the base classes from quadkit.contracts.mcp.exceptions.
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
