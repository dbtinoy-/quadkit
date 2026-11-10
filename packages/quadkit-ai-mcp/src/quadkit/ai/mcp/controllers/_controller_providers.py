"""Controller-backed MCP provider implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.ai.mcp.controllers._internal import (
    _build_input_schema,
    _match_uri_pattern,
)

if TYPE_CHECKING:
    from quadkit.ai.mcp.controllers.base import MCPController


class ControllerToolProvider:
    """MCPToolProviderProtocol backed by a list of MCPController instances.

    Aggregates all ``@tool``-decorated methods across multiple controllers,
    auto-generates JSON Schema from type annotations, and dispatches
    ``call_tool`` to the matching handler.
    """

    def __init__(self, controller_instances: list[MCPController]) -> None:
        """Initialize with a list of already-constructed controller instances.

        Args:
            controller_instances: Instantiated MCPController objects to aggregate.
        """
        self._controllers = controller_instances
        self._tool_map: dict[str, tuple[MCPController, str]] = {}
        for ctrl in controller_instances:
            for info in ctrl.collect_tools():
                self._tool_map[info["name"]] = (ctrl, info["handler_name"])

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools from all registered controllers in MCP format.

        Returns:
            MCP tool definitions with ``name``, ``description``, ``inputSchema``.
        """
        tools = []
        for ctrl in self._controllers:
            for info in ctrl.collect_tools():
                handler = getattr(ctrl, info["handler_name"])
                tools.append(
                    {
                        "name": info["name"],
                        "description": info["description"],
                        "inputSchema": _build_input_schema(handler),
                    }
                )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch a tool call to the matching controller method.

        Args:
            name: MCP tool name.
            arguments: Argument dict from the MCP client.

        Returns:
            Handler return value.

        Raises:
            MCPToolCallError: If no tool with the given name is registered.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        if name not in self._tool_map:
            raise MCPToolCallError(
                message=f"Unknown tool: {name!r}",
                tool_name=name,
            )
        ctrl, handler_name = self._tool_map[name]
        return await getattr(ctrl, handler_name)(**arguments)


class ControllerResourceProvider:
    """MCPResourceProviderProtocol backed by a list of MCPController instances.

    Aggregates all ``@resource``-decorated methods, exposes them for listing,
    and routes ``read_resource`` calls via URI pattern matching.
    """

    def __init__(self, controller_instances: list[MCPController]) -> None:
        """Initialize with a list of already-constructed controller instances.

        Args:
            controller_instances: Instantiated MCPController objects to aggregate.
        """
        self._controllers = controller_instances
        self._resource_map: dict[str, tuple[MCPController, str]] = {}
        for ctrl in controller_instances:
            for info in ctrl.collect_resources():
                self._resource_map[info["uri_pattern"]] = (ctrl, info["handler_name"])

    async def list_resources(self) -> list[dict[str, Any]]:
        """List all resources from all registered controllers in MCP format.

        Returns:
            MCP resource definitions with ``uri``, ``name``, ``description``.
        """
        resources = []
        for ctrl in self._controllers:
            for info in ctrl.collect_resources():
                resources.append(
                    {
                        "uri": info["uri_pattern"],
                        "name": info["name"],
                        "description": info["description"],
                    }
                )
        return resources

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Read a resource by URI, matching exact URIs and ``{var}`` patterns.

        Args:
            uri: Concrete URI from the MCP client (e.g. ``"users://123"``).

        Returns:
            Resource content dict.

        Raises:
            MCPResourceError: If no resource pattern matches the given URI.
        """
        from quadkit.contracts.mcp.exceptions import MCPResourceError

        if uri in self._resource_map:
            ctrl, handler_name = self._resource_map[uri]
            return await getattr(ctrl, handler_name)(uri)

        for pattern, (ctrl, handler_name) in self._resource_map.items():
            kwargs = _match_uri_pattern(pattern, uri)
            if kwargs is not None:
                return await getattr(ctrl, handler_name)(**kwargs)

        raise MCPResourceError(
            message=f"No resource registered for URI: {uri!r}",
            uri=uri,
        )

    async def list_templates(self) -> list[dict[str, Any]]:
        """List URI templates for resources that contain ``{var}`` placeholders.

        Returns:
            MCP URI template definitions with ``uriTemplate``, ``name``, ``description``.
        """
        templates = []
        for ctrl in self._controllers:
            for info in ctrl.collect_resources():
                if "{" in info["uri_pattern"]:
                    templates.append(
                        {
                            "uriTemplate": info["uri_pattern"],
                            "name": info["name"],
                            "description": info["description"],
                        }
                    )
        return templates


class ControllerPromptProvider:
    """MCPPromptProviderProtocol backed by a list of MCPController instances.

    Aggregates all ``@prompt``-decorated methods and dispatches
    ``get_prompt`` calls to the matching handler.
    """

    def __init__(self, controller_instances: list[MCPController]) -> None:
        """Initialize with a list of already-constructed controller instances.

        Args:
            controller_instances: Instantiated MCPController objects to aggregate.
        """
        self._controllers = controller_instances
        self._prompt_map: dict[str, tuple[MCPController, str]] = {}
        for ctrl in controller_instances:
            for info in ctrl.collect_prompts():
                self._prompt_map[info["name"]] = (ctrl, info["handler_name"])

    async def list_prompts(self) -> list[dict[str, Any]]:
        """List all prompt templates from registered controllers in MCP format.

        Returns:
            MCP prompt definitions with ``name``, ``description``, ``arguments``.
        """
        prompts = []
        for ctrl in self._controllers:
            for info in ctrl.collect_prompts():
                prompts.append(
                    {
                        "name": info["name"],
                        "description": info["description"],
                        "arguments": [],
                    }
                )
        return prompts

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get a prompt template by name with arguments filled in.

        Args:
            name: Prompt name.
            arguments: Optional arguments dict from the MCP client.

        Returns:
            MCP-format prompt response with ``description`` and ``messages``.

        Raises:
            MCPPromptError: If no prompt with the given name is registered.
        """
        from quadkit.contracts.mcp.exceptions import MCPPromptError

        if name not in self._prompt_map:
            raise MCPPromptError(
                message=f"Unknown prompt: {name!r}",
                name=name,
            )
        ctrl, handler_name = self._prompt_map[name]
        result = await getattr(ctrl, handler_name)(**(arguments or {}))
        if isinstance(result, str):
            return {
                "description": name,
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": result}}
                ],
            }
        return result
