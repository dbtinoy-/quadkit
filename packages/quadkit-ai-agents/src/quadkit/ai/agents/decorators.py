from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_TOOL_REGISTRY: dict[str, type] = {}
_STRATEGY_REGISTRY: dict[str, type] = {}


def tool(name: str, description: str = "") -> Callable[[type], type]:
    """Register a class as an agent tool with the given name.

    Args:
        name: Unique tool identifier used in the tool registry.
        description: Human-readable description surfaced to the LLM.

    Returns:
        Class decorator that registers the tool.

    Example::

        @tool(name="web_search", description="Search the web for information")
        class WebSearchTool:
            async def execute(self, query: str) -> str:
                ...
    """

    def decorator(cls: type) -> type:
        if name in _TOOL_REGISTRY:
            raise ValueError("Tool already registered")
        cls._tool_name = name  # type: ignore[attr-defined]
        cls._tool_description = description  # type: ignore[attr-defined]
        _TOOL_REGISTRY[name] = cls
        return cls

    return decorator


def strategy(name: str) -> Callable[[type], type]:
    """Register a class as an agent execution strategy.

    Args:
        name: Unique strategy identifier (e.g. ``"react"``, ``"plan_execute"``).

    Returns:
        Class decorator that registers the strategy.

    Example::

        @strategy(name="react")
        class ReActStrategy:
            async def execute(self, goal: str) -> AgentResponse: ...
    """

    def decorator(cls: type) -> type:
        if name in _STRATEGY_REGISTRY:
            raise ValueError("Strategy already registered")
        cls._strategy_name = name  # type: ignore[attr-defined]
        _STRATEGY_REGISTRY[name] = cls
        return cls

    return decorator


__all__ = ["strategy", "tool"]
