"""Service-backed MCP provider implementations and provider combinators."""

from __future__ import annotations

import inspect
from typing import Any

from quadkit.ai.mcp.controllers._internal import _build_input_schema


class ServiceToolProvider:
    """Tool provider that auto-exposes public methods of service instances as MCP tools.

    Created via :meth:`MCPModule.from_services` or directly::

        provider = ServiceToolProvider.from_services(
            [user_service, analytics_service],
            include_patterns=["search", "get_*"],
        )

    Tool names are prefixed with the lowercase service class name to avoid
    collisions (e.g. ``UserService.search_users()`` → ``"userservice_search_users"``).
    The first line of each method's docstring is used as the tool description.
    Both ``async def`` and plain ``def`` methods are supported.
    """

    def __init__(self, entries: list[tuple[Any, str, str, str]]) -> None:
        """Initialize with pre-built tool entries.

        Args:
            entries: List of ``(instance, method_name, tool_name, description)`` tuples.
        """
        self._entries = entries
        self._dispatch: dict[str, tuple[Any, str]] = {
            tool_name: (instance, method_name)
            for instance, method_name, tool_name, _ in entries
        }

    @classmethod
    def from_services(
        cls,
        service_instances: Any,
        include_patterns: list[str] | None = None,
    ) -> ServiceToolProvider:
        """Scan *service_instances* and expose matching public methods as tools.

        Args:
            service_instances: A single instantiated service object or a list.
            include_patterns: Glob patterns to filter method names
                              (e.g. ``["search", "get_*"]``).  When ``None``,
                              all public non-dunder methods are included.

        Returns:
            A new ``ServiceToolProvider`` with entries for every matched method.
        """
        import fnmatch as _fnmatch

        if not isinstance(service_instances, (list, tuple)):
            service_instances = [service_instances]

        entries: list[tuple[Any, str, str, str]] = []
        for instance in service_instances:
            prefix = type(instance).__name__.lstrip("_").lower()
            for attr_name in sorted(dir(type(instance))):
                if attr_name.startswith("_"):
                    continue
                attr = getattr(type(instance), attr_name, None)
                if attr is None or not callable(attr):
                    continue
                if include_patterns is not None and not any(
                    _fnmatch.fnmatch(attr_name, p) for p in include_patterns
                ):
                    continue
                bound = getattr(instance, attr_name)
                tool_name = f"{prefix}_{attr_name}"
                doc = inspect.getdoc(bound) or ""
                description = doc.split("\n")[0] if doc else ""
                entries.append((instance, attr_name, tool_name, description))
        return cls(entries)

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool definitions for all discovered service methods."""
        tools = []
        for instance, method_name, tool_name, description in self._entries:
            bound = getattr(instance, method_name)
            tools.append(
                {
                    "name": tool_name,
                    "description": description,
                    "inputSchema": _build_input_schema(bound),
                }
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Invoke the service method mapped to *name*.

        Args:
            name: Tool name.
            arguments: Arguments dict from the MCP client.

        Returns:
            Method return value (sync or awaited coroutine).

        Raises:
            MCPToolCallError: If no method is registered under *name*.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        entry = self._dispatch.get(name)
        if entry is None:
            raise MCPToolCallError(
                message=f"Unknown tool: {name!r}",
                tool_name=name,
            )
        instance, method_name = entry
        result = getattr(instance, method_name)(**arguments)
        if inspect.iscoroutine(result):
            result = await result
        return result


class _CombinedToolProvider:
    """Internal: chains multiple tool providers into a single interface.

    Used by :class:`~quadkit.ai.mcp.di.MCPProvider` when both
    ``controllers=`` and ``services=`` are active.
    """

    def __init__(self, providers: list[Any]) -> None:
        """Initialize with a list of tool provider instances."""
        self._providers = providers

    async def list_tools(self) -> list[dict[str, Any]]:
        """Aggregate tool definitions from all child providers."""
        result: list[dict[str, Any]] = []
        for p in self._providers:
            result.extend(await p.list_tools())
        return result

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch to the first provider that owns *name*.

        Raises:
            MCPToolCallError: If no provider owns the tool.
        """
        from quadkit.contracts.mcp.exceptions import MCPToolCallError

        for p in self._providers:
            tools = await p.list_tools()
            if any(t["name"] == name for t in tools):
                return await p.call_tool(name, arguments)
        raise MCPToolCallError(
            message=f"Unknown tool: {name!r}",
            tool_name=name,
        )


class _CombinedResourceProvider:
    """Internal: chains multiple resource providers into a single interface.

    Used by :class:`~quadkit.ai.mcp.di.MCPProvider` when both controllers
    and built-in connectors expose resources.
    """

    def __init__(self, providers: list[Any]) -> None:
        """Initialize with a list of resource provider instances."""
        self._providers = [p for p in providers if p is not None]

    async def list_resources(self) -> list[dict[str, Any]]:
        """Aggregate resource definitions from all child providers."""
        result: list[dict[str, Any]] = []
        for p in self._providers:
            result.extend(await p.list_resources())
        return result

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """Delegate to the first provider that owns *uri*.

        Args:
            uri: Resource URI to read.

        Returns:
            MCP resource content dict.

        Raises:
            MCPResourceError: If no provider owns the URI.
        """
        from quadkit.ai.mcp.controllers._internal import _match_uri_pattern
        from quadkit.contracts.mcp.exceptions import MCPResourceError

        # Listed URIs may be ``{var}`` templates (controller resources);
        # ownership must be matched against the template, not only
        # exact-equality, or concrete URIs never route to their owner.
        for p in self._providers:
            resources = await p.list_resources()
            for r in resources:
                uri_pattern = r.get("uri", "")
                if uri_pattern == uri or (
                    "{" in uri_pattern
                    and _match_uri_pattern(uri_pattern, uri) is not None
                ):
                    return await p.read_resource(uri)
        raise MCPResourceError(
            message=f"Unknown resource URI: {uri!r}",
            uri=uri,
        )
