"""Adapter for consuming MCP tools as Quadkit agent tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.ai.mcp.client.core import MCPClient
    from quadkit.contracts.ai.agents import ToolRegistryProtocol

logger = get_logger(__name__)


class MCPToolAdapter:
    """Adapter that wraps an MCP tool into a Quadkit ToolProtocol.

    Allows Quadkit agents to natively invoke tools hosted on an
    external MCP server.
    """

    def __init__(
        self,
        client: MCPClient,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
    ) -> None:
        """Initialize the MCP tool adapter.

        Args:
            client: The MCP client connected to the server.
            name: The tool name.
            description: The tool description.
            parameters_schema: The JSON Schema for the tool parameters.
        """
        self._client = client
        self._name = name
        self._description = description
        self._parameters_schema = parameters_schema

    @property
    def name(self) -> str:
        """Unique tool identifier."""
        return self._name

    @property
    def description(self) -> str:
        """Human-readable description for the LLM."""
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema describing the tool's parameters."""
        return self._parameters_schema

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool via the MCP client."""
        logger.debug("mcp_tool_executing", tool=self._name)
        result = await self._client.call_tool(self._name, kwargs)

        # Determine if it's an error result
        if result.is_error:
            # Raise an exception so the agent executor handles it
            raise RuntimeError(f"MCP tool {self._name} failed: {result.content}")

        # Parse content from MCPToolResult into a native string or format
        if not result.content:
            return None

        if len(result.content) == 1 and result.content[0].get("type") == "text":
            return result.content[0].get("text")

        return result.content


async def register_mcp_tools(
    client: MCPClient,
    registry: ToolRegistryProtocol,
    module_class: type | None = None,
) -> int:
    """Discover tools from an MCP server and register them.

    Args:
        client: The MCP client (must be initialized/started).
        registry: The tool registry to populate.
        module_class: Optional module class to bind the tools to.

    Returns:
        Number of tools registered.
    """
    try:
        tools = await client.list_tools()
        count = 0
        for tool in tools:
            adapter = MCPToolAdapter(
                client=client,
                name=tool["name"],
                description=tool.get("description", "") or "",
                parameters_schema=tool.get("inputSchema", {}),
            )
            registry.register(adapter, module_class=module_class)
            count += 1

        logger.info(
            "mcp_tools_registered",
            count=count,
            server=getattr(client, "_server_name", "unknown"),
        )
        return count
    except Exception as exc:  # noqa: BLE001 — tool registration is best-effort
        logger.error("mcp_tools_registration_failed", error_type=type(exc).__name__)
        return 0


__all__ = ["MCPToolAdapter", "register_mcp_tools"]
