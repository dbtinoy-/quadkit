"""MCPController base class for grouping MCP tools, resources, and prompts."""

from __future__ import annotations

from typing import Any

__all__ = ["MCPController"]


class MCPController:
    """Base class for MCP controllers.

    Groups related MCP tools, resources, and prompt templates into a single
    class — mirroring the ``Controller`` DX from quadkit-web.  Register
    decorated subclasses via ``MCPModule(controllers=[...])``.

    Example::

        class DataToolsController(MCPController):
            def __init__(self, repo: UserRepository) -> None:
                self.repo = repo

            @tool("get_user", description="Fetch a user by ID")
            async def get_user(self, user_id: str) -> dict:
                result = await self.repo.get(user_id)
                return result.unwrap_or({})
    """

    @classmethod
    def collect_tools(cls) -> list[dict[str, Any]]:
        """Collect tool-decorated methods from the class hierarchy.

        Returns:
            List of dicts with keys ``name``, ``description``, ``handler_name``.
        """
        tools: list[dict[str, Any]] = []
        seen: set[str] = set()
        for klass in cls.__mro__:
            if klass is MCPController or klass is object:
                continue
            for attr_name in dir(klass):
                if attr_name.startswith("_") or attr_name in seen:
                    continue
                attr = getattr(klass, attr_name, None)
                if attr is not None and hasattr(attr, "_tool_config"):
                    tools.append({**attr._tool_config, "handler_name": attr_name})
                    seen.add(attr_name)
        return tools

    @classmethod
    def collect_resources(cls) -> list[dict[str, Any]]:
        """Collect resource-decorated methods from the class hierarchy.

        Returns:
            List of dicts with keys ``uri_pattern``, ``name``, ``description``,
            ``handler_name``.
        """
        resources: list[dict[str, Any]] = []
        seen: set[str] = set()
        for klass in cls.__mro__:
            if klass is MCPController or klass is object:
                continue
            for attr_name in dir(klass):
                if attr_name.startswith("_") or attr_name in seen:
                    continue
                attr = getattr(klass, attr_name, None)
                if attr is not None and hasattr(attr, "_resource_config"):
                    resources.append(
                        {**attr._resource_config, "handler_name": attr_name}
                    )
                    seen.add(attr_name)
        return resources

    @classmethod
    def collect_prompts(cls) -> list[dict[str, Any]]:
        """Collect prompt-decorated methods from the class hierarchy.

        Returns:
            List of dicts with keys ``name``, ``description``, ``handler_name``.
        """
        prompts: list[dict[str, Any]] = []
        seen: set[str] = set()
        for klass in cls.__mro__:
            if klass is MCPController or klass is object:
                continue
            for attr_name in dir(klass):
                if attr_name.startswith("_") or attr_name in seen:
                    continue
                attr = getattr(klass, attr_name, None)
                if attr is not None and hasattr(attr, "_prompt_config"):
                    prompts.append({**attr._prompt_config, "handler_name": attr_name})
                    seen.add(attr_name)
        return prompts
