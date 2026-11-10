"""@tool decorator — converts async functions into agent tools."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from quadkit.ai.agents.tools.schema import generate_json_schema


def tool(
    func: Callable | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Any:
    """Decorator that converts an async function into an agent tool.

    Automatically generates JSON schema from type hints for LLM
    function calling.

    Usage::

        @tool
        async def lookup_order(order_id: str) -> dict:
            \"\"\"Look up an order by its ID.\"\"\"
            return await order_service.find(order_id)

        @tool(name="search", description="Search local services")
        async def search_services(
            query: str,
            category: str | None = None,
            radius_km: float = 5.0,
        ) -> list[dict]:
            return await search.find(query, category, radius_km)
    """

    def decorator(fn: Callable) -> FunctionTool:
        tool_name = name or fn.__name__
        tool_description = description or inspect.getdoc(fn) or ""

        # Extract first line of docstring as description
        if "\n" in tool_description:
            tool_description = tool_description.split("\n")[0].strip()

        # Generate JSON schema from type hints + Google-style docstring
        schema = generate_json_schema(fn)

        return FunctionTool(
            fn=fn,
            tool_name=tool_name,
            tool_description=tool_description,
            schema=schema,
        )

    if func is not None:
        return decorator(func)
    return decorator


class FunctionTool:
    """Tool wrapping an async function with auto-generated schema."""

    def __init__(
        self,
        fn: Callable,
        tool_name: str,
        tool_description: str,
        schema: dict[str, Any],
    ) -> None:
        self._fn = fn
        self._name = tool_name
        self._description = tool_description
        self._schema = schema

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return self._schema

    async def execute(self, **kwargs: Any) -> Any:
        return await self._fn(**kwargs)

    def __repr__(self) -> str:
        return f"FunctionTool({self._name})"
