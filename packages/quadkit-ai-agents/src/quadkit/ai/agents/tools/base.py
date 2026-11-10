"""Base Tool class for class-based tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from quadkit.contracts.ai.agents import ToolProtocol


class AbstractTool(ABC, ToolProtocol):
    """Abstract base class for class-based agent tools.

    Subclass this to create tools with more complex behavior
    than simple function wrappers.

    Example::

        class OrderLookupTool(AbstractTool):
            def __init__(self, order_service: OrderService):
                self.order_service = order_service

            @property
            def name(self) -> str:
                return "lookup_order"

            @property
            def description(self) -> str:
                return "Look up an order by its ID"

            @property
            def parameters_schema(self) -> dict[str, Any]:
                return {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"}
                    },
                    "required": ["order_id"]
                }

            async def execute(self, **kwargs: Any) -> Any:
                order_id = kwargs.get("order_id")
                return await self.order_service.find(order_id)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool identifier. Must be implemented by subclass."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for the LLM. Must be implemented by subclass."""

    @property
    @abstractmethod
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema describing the tool's parameters. Must be implemented by subclass."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with the given arguments. Must be implemented by subclass."""


__all__ = ["AbstractTool"]
