"""Tool adapter for bridging quadkit-agents with MCP.

Architecture Decision (P4.1)
----------------------------
The ``@tool`` decorator and ``ToolProtocol`` already produce JSON Schema via
``parameters_schema`` — the same format MCP uses for ``inputSchema``.  The
adapter performs **property-name mapping only** (no schema transformation),
keeping agent tooling decoupled from the MCP transport layer.  This is
intentional: agents should not depend on MCP, and MCP should not dictate the
internal tool API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.ai.agents import ToolRegistryProtocol


class ToolRegistryAdapter:
    """Adapter that bridges quadkit-agents ToolRegistry to MCPToolProviderProtocol.

    This adapter allows the MCP server to use the @tool-decorated
    functions from quadkit-agents.  The translation is minimal:

    * ``ToolProtocol.parameters_schema`` → MCP ``inputSchema``
    * ``ToolRegistryProtocol.get()``     → lookup by name
    * ``ToolProtocol.execute(**kw)``     → tool invocation
    """

    def __init__(
        self,
        tool_registry: ToolRegistryProtocol | None = None,
    ) -> None:
        self._registry = tool_registry

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools in MCP format.

        Returns:
            List of tool definitions with ``name``, ``description``,
            and ``inputSchema`` (JSON Schema produced by ``@tool``).
        """
        if self._registry is None:
            return []

        try:
            tools = self._registry.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.parameters_schema,
                }
                for t in tools
            ]
        except Exception:  # noqa: BLE001 — tool conversion falls back to an empty list
            return []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Execute a tool by name with given arguments.

        Args:
            name: Name of the tool to call.
            arguments: Arguments to pass to the tool.

        Returns:
            Tool execution result.
        """
        if self._registry is None:
            raise RuntimeError("No tool registry configured")

        tool = self._registry.get(name)
        if tool is None:
            raise ValueError(f"Tool not found: {name}")

        return await tool.execute(**arguments)


__all__ = ["ToolRegistryAdapter"]
