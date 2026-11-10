"""Root hook payload surface for quadkit-ai-mcp.

Defines canonical payload dataclasses for MCP server/client lifecycle hook
points. Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "MCPServerStartedHook",
    "MCPServerStoppedHook",
    "MCPToolInvokedHook",
]


@dataclass(frozen=True, kw_only=True)
class MCPServerStartedHook:
    """Payload fired after the MCP server completes its startup sequence.

    Attributes:
        transport: Transport type in use (e.g. ``"stdio"`` or ``"sse"``).
    """

    transport: str


@dataclass(frozen=True, kw_only=True)
class MCPServerStoppedHook:
    """Payload fired after the MCP server shuts down.

    Attributes:
        transport: Transport type that was in use at shutdown.
    """

    transport: str


@dataclass(frozen=True, kw_only=True)
class MCPToolInvokedHook:
    """Payload fired each time a tool is invoked through the MCP protocol.

    Attributes:
        tool_name: Name of the MCP tool that was called.
    """

    tool_name: str
