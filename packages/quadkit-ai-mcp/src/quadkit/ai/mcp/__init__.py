"""the optional provider — MCP Server for Quadkit Framework.

Canonical import paths
-----------------------
MCPServer:         from quadkit.ai.mcp import MCPServer
MCPClient:         from quadkit.ai.mcp import MCPClient
MCPConfig:        from quadkit.ai.mcp import MCPConfig
ToolHandler:      from quadkit.ai.mcp import ToolHandler
ResourceHandler:  from quadkit.ai.mcp import ResourceHandler
PromptHandler:    from quadkit.ai.mcp import PromptHandler
StdioTransport:   from quadkit.ai.mcp import StdioTransport
SSETransport:     from quadkit.ai.mcp import SSETransport
MCPModule:        from quadkit.ai.mcp import MCPModule
MCPProvider:       from quadkit.ai.mcp import MCPProvider

Quick Start
-----------

    from quadkit.ai.mcp import MCPServer, MCPModule
    from quadkit import QuadkitApplication

    app = QuadkitApplication(
        modules=[..., MCPModule()],
    )

    await app.run()
"""

from __future__ import annotations

import importlib.metadata
import pkgutil
from typing import TYPE_CHECKING, Any

__path__ = pkgutil.extend_path(__path__, __name__)

from quadkit.ai.mcp.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.ai.mcp import MCPModule  # type: ignore[attr-defined]
    from quadkit.ai.mcp.adapters import ToolRegistryAdapter
    from quadkit.ai.mcp.client.core import (
        MCPClient,
        MCPClientTransport,
        SSEClientTransport,
        StdioClientTransport,
    )
    from quadkit.ai.mcp.client.module import (
        MCPClientModule,
        MCPClientProvider,
        MCPClientRegistry,
        MCPConnection,
    )
    from quadkit.ai.mcp.config import MCPConfig
    from quadkit.ai.mcp.controllers import (
        ControllerPromptProvider,
        ControllerResourceProvider,
        ControllerToolProvider,
        MCPController,
        ModulePromptProvider,
        ModuleResourceProvider,
        ModuleToolProvider,
        ServiceToolProvider,
    )
    from quadkit.ai.mcp.decorators import (
        prompt,
        resource,
        tool,
    )
    from quadkit.ai.mcp.di.provider import MCPProvider
    from quadkit.ai.mcp.exceptions import (
        MCPError,
        MCPInitializationError,
        MCPMethodNotFoundError,
        MCPPromptError,
        MCPProtocolError,
        MCPResourceError,
        MCPToolCallError,
        MCPTransportError,
    )
    from quadkit.ai.mcp.hooks import (
        MCPServerStartedHook,
        MCPServerStoppedHook,
        MCPToolInvokedHook,
    )
    from quadkit.ai.mcp.protocols import (
        MCPPromptHandlerProtocol,
        MCPPromptProviderProtocol,
        MCPResourceHandlerProtocol,
        MCPResourceProviderProtocol,
        MCPServerProtocol,
        MCPToolHandlerProtocol,
        MCPToolProviderProtocol,
        MCPTransportProtocol,
    )
    from quadkit.ai.mcp.server import MCPServer
    from quadkit.ai.mcp.server.handlers import (
        PromptHandler,
        ResourceHandler,
        ToolHandler,
    )
    from quadkit.ai.mcp.transport import (
        AbstractTransport,
        SSETransport,
        StdioTransport,
    )
    from quadkit.ai.mcp.types import (
        MCPInitializeResult,
        MCPJSONRPCRequest,
        MCPJSONRPCResponse,
        MCPPrompt,
        MCPPromptMessage,
        MCPResource,
        MCPResourceContent,
        MCPServerCapabilities,
        MCPServerInfo,
        MCPToolDefinition,
        MCPToolResult,
    )

_LAZY_IMPORTS: dict[str, str] = {
    "AbstractTransport": "quadkit.ai.mcp.transport",
    "ControllerPromptProvider": "quadkit.ai.mcp.controllers",
    "ControllerResourceProvider": "quadkit.ai.mcp.controllers",
    "ControllerToolProvider": "quadkit.ai.mcp.controllers",
    # Hooks
    "MCPServerStartedHook": "quadkit.ai.mcp.hooks",
    "MCPServerStoppedHook": "quadkit.ai.mcp.hooks",
    "MCPToolInvokedHook": "quadkit.ai.mcp.hooks",
    "MCPController": "quadkit.ai.mcp.controllers",
    "MCPInitializeResult": "quadkit.ai.mcp.types",
    "MCPJSONRPCRequest": "quadkit.ai.mcp.types",
    "MCPJSONRPCResponse": "quadkit.ai.mcp.types",
    "MCPPrompt": "quadkit.ai.mcp.types",
    "MCPPromptMessage": "quadkit.ai.mcp.types",
    "MCPResource": "quadkit.ai.mcp.types",
    "MCPResourceContent": "quadkit.ai.mcp.types",
    "MCPServerCapabilities": "quadkit.ai.mcp.types",
    "MCPServerInfo": "quadkit.ai.mcp.types",
    "MCPToolDefinition": "quadkit.ai.mcp.types",
    "MCPToolResult": "quadkit.ai.mcp.types",
    "ModulePromptProvider": "quadkit.ai.mcp.controllers",
    "ModuleResourceProvider": "quadkit.ai.mcp.controllers",
    "ModuleToolProvider": "quadkit.ai.mcp.controllers",
    "ServiceToolProvider": "quadkit.ai.mcp.controllers",
    "MCPClient": "quadkit.ai.mcp.client.core",
    "MCPClientModule": "quadkit.ai.mcp.client.module",
    "MCPClientProvider": "quadkit.ai.mcp.client.module",
    "MCPClientRegistry": "quadkit.ai.mcp.client.module",
    "MCPConnection": "quadkit.ai.mcp.client.module",
    "MCPClientTransport": "quadkit.ai.mcp.client.core",
    "MCPConfig": "quadkit.ai.mcp.config",
    "MCPError": "quadkit.ai.mcp.exceptions",
    "MCPInitializationError": "quadkit.ai.mcp.exceptions",
    "MCPMethodNotFoundError": "quadkit.ai.mcp.exceptions",
    "MCPModule": "quadkit.ai.mcp.module",
    "MCPPromptError": "quadkit.ai.mcp.exceptions",
    "MCPProtocolError": "quadkit.ai.mcp.exceptions",
    "MCPProvider": "quadkit.ai.mcp.di.provider",
    "MCPResourceError": "quadkit.ai.mcp.exceptions",
    "MCPServer": "quadkit.ai.mcp.server",
    "MCPToolCallError": "quadkit.ai.mcp.exceptions",
    "MCPTransportError": "quadkit.ai.mcp.exceptions",
    # Protocols
    "MCPToolProviderProtocol": "quadkit.ai.mcp.protocols",
    "MCPResourceProviderProtocol": "quadkit.ai.mcp.protocols",
    "MCPPromptProviderProtocol": "quadkit.ai.mcp.protocols",
    "MCPTransportProtocol": "quadkit.ai.mcp.protocols",
    "MCPServerProtocol": "quadkit.ai.mcp.protocols",
    "MCPToolHandlerProtocol": "quadkit.ai.mcp.protocols",
    "MCPResourceHandlerProtocol": "quadkit.ai.mcp.protocols",
    "MCPPromptHandlerProtocol": "quadkit.ai.mcp.protocols",
    "PromptHandler": "quadkit.ai.mcp.server.handlers",
    "ResourceHandler": "quadkit.ai.mcp.server.handlers",
    "SSETransport": "quadkit.ai.mcp.transport",
    "SSEClientTransport": "quadkit.ai.mcp.client.core",
    "StdioClientTransport": "quadkit.ai.mcp.client.core",
    "StdioTransport": "quadkit.ai.mcp.transport",
    "ToolHandler": "quadkit.ai.mcp.server.handlers",
    "ToolRegistryAdapter": "quadkit.ai.mcp.adapters",
    "prompt": "quadkit.ai.mcp.decorators",
    "resource": "quadkit.ai.mcp.decorators",
    "tool": "quadkit.ai.mcp.decorators",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib as _importlib

        module = _importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = [
    "AbstractTransport",
    "ControllerPromptProvider",
    "ControllerResourceProvider",
    "ControllerToolProvider",
    "MCPClient",
    "MCPClientModule",
    "MCPClientProvider",
    "MCPClientRegistry",
    "MCPClientTransport",
    "MCPConfig",
    "MCPConnection",
    "MCPController",
    "MCPError",
    "MCPInitializationError",
    "MCPInitializeResult",
    "MCPJSONRPCRequest",
    "MCPJSONRPCResponse",
    "MCPMethodNotFoundError",
    "MCPModule",
    "MCPPrompt",
    "MCPPromptError",
    "MCPPromptHandlerProtocol",
    "MCPPromptMessage",
    "MCPPromptProviderProtocol",
    "MCPProtocolError",
    "MCPProvider",
    "MCPResource",
    "MCPResourceContent",
    "MCPResourceError",
    "MCPResourceHandlerProtocol",
    "MCPResourceProviderProtocol",
    "MCPServer",
    "MCPServerCapabilities",
    "MCPServerInfo",
    "MCPServerProtocol",
    "MCPServerStartedHook",
    "MCPServerStoppedHook",
    "MCPToolCallError",
    "MCPToolDefinition",
    "MCPToolHandlerProtocol",
    "MCPToolInvokedHook",
    "MCPToolProviderProtocol",
    "MCPTransportProtocol",
    "ModulePromptProvider",
    "ModuleResourceProvider",
    "ModuleToolProvider",
    "PromptHandler",
    "ResourceHandler",
    "SSEClientTransport",
    "SSETransport",
    "ServiceToolProvider",
    "StdioClientTransport",
    "StdioTransport",
    "ToolHandler",
    "ToolRegistryAdapter",
    "prompt",
    "resource",
    "tool",
]
