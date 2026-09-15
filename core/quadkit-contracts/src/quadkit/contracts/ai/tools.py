"""Tools + LCEL contracts for G-03 parity.

Defines tool decorators and classes analogous to LangChain's tool system.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any


@dataclass(frozen=True)
class Tool:
    """Base tool class (like LangChain's BaseTool).

    Attributes:
        name: Tool name.
        description: Tool description.
        func: The underlying function.
    """

    name: str
    description: str = ""
    func: Callable[..., Any] | None = None

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronously invoke the tool."""
        if self.func is None:
            raise ValueError("Tool function not set")
        return self.func(*args, **kwargs)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronously invoke the tool."""
        if self.func is None:
            raise ValueError("Tool function not set")
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)
        return self.func(*args, **kwargs)


class StructuredTool:
    """Tool with structured input/output (like LangChain's StructuredTool).

    Analogous to LangChain's StructuredTool for tools with typed parameters.
    """

    def __init__(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
    ) -> None:
        self.name = name
        self.description = description
        self.func = func

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        """Synchronously invoke the tool."""
        return self.func(*args, **kwargs)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        """Asynchronously invoke the tool."""
        if asyncio.iscoroutinefunction(self.func):
            return await self.func(*args, **kwargs)
        return self.func(*args, **kwargs)


def tool(name: str | None = None) -> Callable[[Callable[..., Any]], Tool]:
    """Decorator to create a tool from a function (like @tool).

    Args:
        name: Optional tool name. Defaults to function name.

    Returns:
        A decorator that creates a Tool from a function.

    Example:
        @tool("add")
        def add(a: int, b: int) -> int:
            '''Add two numbers.'''
            return a + b
    """

    def decorator(func: Callable[..., Any]) -> Tool:
        tool_name = name or func.__name__
        tool_description = func.__doc__ or ""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return Tool(
            name=tool_name,
            description=tool_description.strip(),
            func=func,
        )

    return decorator


__all__ = [
    "StructuredTool",
    "Tool",
    "tool",
]
