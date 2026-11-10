"""Re-export MCP protocols for consumer convenience.

Consumers use these contracts to depend on MCP abstractions without
importing the full quadkit-ai-mcp implementation.
"""

from __future__ import annotations

from quadkit.contracts.mcp.protocols import (
    MCPAuthorizerProtocol as MCPAuthorizerProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPPromptHandlerProtocol as MCPPromptHandlerProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPPromptProviderProtocol as MCPPromptProviderProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPResourceHandlerProtocol as MCPResourceHandlerProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPResourceProviderProtocol as MCPResourceProviderProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPServerProtocol as MCPServerProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPToolHandlerProtocol as MCPToolHandlerProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPToolProviderProtocol as MCPToolProviderProtocol,
)
from quadkit.contracts.mcp.protocols import (
    MCPTransportProtocol as MCPTransportProtocol,
)

__all__ = [
    "MCPAuthorizerProtocol",
    "MCPPromptHandlerProtocol",
    "MCPPromptProviderProtocol",
    "MCPResourceHandlerProtocol",
    "MCPResourceProviderProtocol",
    "MCPServerProtocol",
    "MCPToolHandlerProtocol",
    "MCPToolProviderProtocol",
    "MCPTransportProtocol",
]
