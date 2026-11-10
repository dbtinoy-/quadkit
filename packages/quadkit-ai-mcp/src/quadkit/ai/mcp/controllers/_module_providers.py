"""Module-backed MCP provider implementations."""

from __future__ import annotations

from typing import Any

from quadkit.ai.mcp.controllers._internal import (
    _build_input_schema,
    _match_uri_pattern,
)


class ModuleToolProvider:
    """Tool provider built from module-level ``@tool``-decorated functions.

    Use :meth:`from_module` to scan a Python module for decorated callables::

        import my_tools
        provider = ModuleToolProvider.from_module(my_tools)

    Or pass functions directly::

        provider = ModuleToolProvider([search_users, create_user])
    """

    def __init__(self, funcs: list[Any]) -> None:
        """Initialize with a list of decorated functions.

        Args:
            funcs: Callables that have ``_tool_config`` set by ``@tool()``.
        """
        self._tool_map: dict[str, Any] = {}
        for func in funcs:
            cfg = getattr(func, "_tool_config", None)
            if cfg:
                self._tool_map[cfg["name"]] = func

    @classmethod
    def from_module(cls, module: Any) -> ModuleToolProvider:
        """Scan *module* for ``@tool``-decorated functions.

        Args:
            module: A Python module object.

        Returns:
            A new ``ModuleToolProvider`` with all discovered tools.
        """
        funcs = [
            obj
            for obj in vars(module).values()
            if callable(obj) and hasattr(obj, "_tool_config")
        ]
        return cls(funcs)

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool definitions for all registered functions."""
        tools = []
        for name, func in self._tool_map.items():
            cfg = func._tool_config
            tools.append(
                {
                    "name": name,
                    "description": cfg["description"],
                    "inputSchema": _build_input_schema(func),
                }
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke the tool function by name.

        Args:
            name: Tool name.
            arguments: Arguments dict from the MCP client.

        Returns:
            Tool result.

        Raises:
            MCPToolCallError: If the tool name is not registered.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        func = self._tool_map.get(name)
        if func is None:
            raise MCPToolCallError(
                message=f"Unknown tool: {name!r}",
                tool_name=name,
            )
        return await func(**arguments)


class ModuleResourceProvider:
    """Resource provider built from module-level ``@resource``-decorated functions.

    Use :meth:`from_module` to scan a Python module for decorated callables.
    """

    def __init__(self, funcs: list[Any]) -> None:
        """Initialize with a list of decorated functions.

        Args:
            funcs: Callables that have ``_resource_config`` set by ``@resource()``.
        """
        self._resource_map: dict[str, Any] = {}
        for func in funcs:
            cfg = getattr(func, "_resource_config", None)
            if cfg:
                self._resource_map[cfg["uri_pattern"]] = func

    @classmethod
    def from_module(cls, module: Any) -> ModuleResourceProvider:
        """Scan *module* for ``@resource``-decorated functions.

        Args:
            module: A Python module object.

        Returns:
            A new ``ModuleResourceProvider`` with all discovered resources.
        """
        funcs = [
            obj
            for obj in vars(module).values()
            if callable(obj) and hasattr(obj, "_resource_config")
        ]
        return cls(funcs)

    async def list_resources(self) -> list[dict[str, Any]]:
        """Return all registered resource definitions."""
        return [
            {
                "uri": func._resource_config["uri_pattern"],
                "name": func._resource_config["name"],
                "description": func._resource_config["description"],
            }
            for func in self._resource_map.values()
        ]

    async def read_resource(self, uri: str) -> Any:
        """Read a resource by URI.

        Args:
            uri: Concrete URI from the MCP client.

        Returns:
            Resource content.

        Raises:
            MCPResourceError: If no resource pattern matches the given URI.
        """
        from quadkit.contracts.mcp.exceptions import MCPResourceError

        if uri in self._resource_map:
            return await self._resource_map[uri](uri)

        for pattern, func in self._resource_map.items():
            kwargs = _match_uri_pattern(pattern, uri)
            if kwargs is not None:
                return await func(**kwargs)

        raise MCPResourceError(
            message=f"No resource registered for URI: {uri!r}",
            uri=uri,
        )

    async def list_templates(self) -> list[dict[str, Any]]:
        """Return URI templates (resources with ``{var}`` placeholders)."""
        return [
            {
                "uriTemplate": func._resource_config["uri_pattern"],
                "name": func._resource_config["name"],
                "description": func._resource_config["description"],
            }
            for func in self._resource_map.values()
            if "{" in func._resource_config["uri_pattern"]
        ]


class ModulePromptProvider:
    """Prompt provider built from module-level ``@prompt``-decorated functions.

    Use :meth:`from_module` to scan a Python module for decorated callables.
    """

    def __init__(self, funcs: list[Any]) -> None:
        """Initialize with a list of decorated functions.

        Args:
            funcs: Callables that have ``_prompt_config`` set by ``@prompt()``.
        """
        self._prompt_map: dict[str, Any] = {}
        for func in funcs:
            cfg = getattr(func, "_prompt_config", None)
            if cfg:
                self._prompt_map[cfg["name"]] = func

    @classmethod
    def from_module(cls, module: Any) -> ModulePromptProvider:
        """Scan *module* for ``@prompt``-decorated functions.

        Args:
            module: A Python module object.

        Returns:
            A new ``ModulePromptProvider`` with all discovered prompts.
        """
        funcs = [
            obj
            for obj in vars(module).values()
            if callable(obj) and hasattr(obj, "_prompt_config")
        ]
        return cls(funcs)

    async def list_prompts(self) -> list[dict[str, Any]]:
        """Return all registered prompt definitions."""
        return [
            {
                "name": func._prompt_config["name"],
                "description": func._prompt_config["description"],
            }
            for func in self._prompt_map.values()
        ]

    async def get_prompt(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> Any:
        """Return a prompt by name.

        Args:
            name: Prompt name.
            arguments: Optional template arguments.

        Returns:
            MCP prompt response dict.

        Raises:
            MCPPromptError: If the prompt name is not registered.
        """
        from quadkit.contracts.mcp.exceptions import MCPPromptError

        func = self._prompt_map.get(name)
        if func is None:
            raise MCPPromptError(
                message=f"Unknown prompt: {name!r}",
                prompt_name=name,
            )
        result = await func(**(arguments or {}))
        if isinstance(result, str):
            return {
                "description": name,
                "messages": [
                    {"role": "user", "content": {"type": "text", "text": result}}
                ],
            }
        return result
