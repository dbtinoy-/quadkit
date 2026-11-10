"""Decorators for registering MCPController methods as tools, resources, and prompts."""

from __future__ import annotations

from typing import Any

__all__ = ["prompt", "resource", "tool"]


def tool(
    name: str,
    *,
    description: str = "",
) -> Any:
    """Register a method as an MCP tool handler.

    Stores ``_tool_config`` on the decorated method for discovery by
    :meth:`~quadkit.ai.mcp.controllers.base.MCPController.collect_tools`.

    Args:
        name: MCP tool name exposed to AI clients.
        description: Human-readable description for the tool schema.

    Returns:
        Decorator that attaches tool metadata to the method.

    Example::

        @tool("search_users", description="Search users by name")
        async def search_users(self, name: str = "") -> list[dict]:
            ...
    """

    def decorator(func: Any) -> Any:
        func._tool_config = {"name": name, "description": description}
        return func

    return decorator


def resource(
    uri_pattern: str,
    *,
    description: str = "",
    name: str | None = None,
) -> Any:
    """Register a method as an MCP resource handler.

    Stores ``_resource_config`` on the decorated method for discovery by
    :meth:`~quadkit.ai.mcp.controllers.base.MCPController.collect_resources`.

    Args:
        uri_pattern: URI template (e.g. ``"users://{user_id}"``).
        description: Human-readable description of the resource.
        name: Optional display name; defaults to the URI pattern.

    Returns:
        Decorator that attaches resource metadata to the method.

    Example::

        @resource("users://{user_id}", description="Expose user by ID")
        async def get_user(self, user_id: str) -> dict:
            ...
    """

    def decorator(func: Any) -> Any:
        func._resource_config = {
            "uri_pattern": uri_pattern,
            "description": description,
            "name": name or uri_pattern,
        }
        return func

    return decorator


def prompt(
    name: str,
    *,
    description: str = "",
) -> Any:
    """Register a method as an MCP prompt template handler.

    Stores ``_prompt_config`` on the decorated method for discovery by
    :meth:`~quadkit.ai.mcp.controllers.base.MCPController.collect_prompts`.

    Args:
        name: MCP prompt name exposed to AI clients.
        description: Human-readable description of the prompt template.

    Returns:
        Decorator that attaches prompt metadata to the method.

    Example::

        @prompt("summarize", description="Generate a summary prompt")
        async def summarize_prompt(self) -> str:
            return "Summarize the following data..."
    """

    def decorator(func: Any) -> Any:
        func._prompt_config = {"name": name, "description": description}
        return func

    return decorator
