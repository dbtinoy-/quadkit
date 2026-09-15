"""MCP protocol definitions.

These protocols define the structural contracts for MCP server
components. Packages can type-hint against these without importing
the concrete implementations from ``quadkit-mcp``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class MCPToolProviderProtocol(Protocol):
    """Protocol for providing tools to the MCP server.

    Satisfied by:
    - ``ToolRegistryAdapter`` (bridges quadkit-agents ToolRegistry)
    - Any custom tool provider
    """

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools in MCP format.

        Returns list of dicts with ``name``, ``description``,
        ``inputSchema`` keys.
        """
        ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a tool by name with given arguments."""
        ...


@runtime_checkable
class MCPResourceProviderProtocol(Protocol):
    """Protocol for providing resources to the MCP server.

    Resources are data that AI clients can browse and read —
    database records, files, configuration, etc.
    """

    async def list_resources(self) -> list[dict[str, Any]]:
        """List available resources in MCP format."""
        ...

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource by URI."""
        ...


@runtime_checkable
class MCPPromptProviderProtocol(Protocol):
    """Protocol for providing prompt templates to the MCP server."""

    async def list_prompts(self) -> list[dict[str, Any]]:
        """List available prompt templates."""
        ...

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get a prompt template with arguments filled."""
        ...


@runtime_checkable
class MCPTransportProtocol(Protocol):
    """Protocol for MCP transport implementations.

    A transport handles the I/O layer — reading requests and
    writing responses. The MCP server is transport-agnostic.
    """

    async def start(self) -> None:
        """Start the transport."""
        ...

    async def stop(self) -> None:
        """Stop the transport."""
        ...


@runtime_checkable
class MCPServerProtocol(Protocol):
    """Protocol for the MCP server.

    The server routes JSON-RPC messages to handlers and returns
    JSON-RPC responses.
    """

    async def handle_message(
        self,
        message: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Handle a JSON-RPC message and return the response.

        Returns None for notifications (no response expected).
        """
        ...


@runtime_checkable
class MCPToolHandlerProtocol(Protocol):
    """Protocol for handling MCP tool-related methods.

    Handles tools/list and tools/call methods.
    """

    async def list_tools(self) -> list[dict[str, Any]]:
        """Handle tools/list method.

        Returns list of available tools with their definitions.
        """
        ...

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle tools/call method.

        Executes a tool and returns the result.
        """
        ...


@runtime_checkable
class MCPResourceHandlerProtocol(Protocol):
    """Protocol for handling MCP resource-related methods.

    Handles resources/list, resources/read, and resources/templates/list.
    """

    async def list_resources(self) -> list[dict[str, Any]]:
        """Handle resources/list method.

        Returns list of available resources.
        """
        ...

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Handle resources/read method.

        Returns content of a specific resource.
        """
        ...

    async def list_templates(self) -> list[dict[str, Any]]:
        """Handle resources/templates/list method.

        Returns list of URI templates for resources.
        """
        ...


@runtime_checkable
class MCPPromptHandlerProtocol(Protocol):
    """Protocol for handling MCP prompt-related methods.

    Handles prompts/list and prompts/get methods.
    """

    async def list_prompts(self) -> list[dict[str, Any]]:
        """Handle prompts/list method.

        Returns list of available prompt templates.
        """
        ...

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Handle prompts/get method.

        Returns a prompt with arguments filled in.
        """
        ...


@runtime_checkable
class MCPAuthorizerProtocol(Protocol):
    """Authorize an initialized client's method invocation.

    Satisfied by any identity/scope resolver the host binds; the
    server core consults it once per non-handshake request.
    """

    async def authorize(
        self,
        method: str,
        params: dict[str, Any],
        client_info: dict[str, Any],
    ) -> bool:
        """Return True to allow dispatch, False to reject with -32000."""
        ...


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
