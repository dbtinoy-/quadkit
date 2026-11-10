from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.agents.tools import ToolBase, tool, ToolRegistryImpl


class TestToolDecorator:
    def test_tool_decorator_creates_tool_wrapper(self) -> None:
        @tool
        async def get_weather(location: str) -> dict:
            """Get weather for a location."""
            return {"location": location, "temp": 72}

        assert "get_weather" == get_weather.name
        assert "Get weather for a location." == get_weather.description

    def test_tool_decorator_with_custom_name(self) -> None:
        @tool(name="weather", description="Get weather info")
        async def get_weather(location: str) -> dict:
            return {"location": location}

        assert "weather" == get_weather.name
        assert "Get weather info" == get_weather.description

    def test_tool_decorator_generates_parameters_schema(self) -> None:
        @tool
        async def search_products(query: str, limit: int = 10) -> list[dict]:
            """Search for products."""
            return [{"query": query, "limit": limit}]

        schema = search_products.parameters_schema
        assert schema["type"] == "object"
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "query" in schema["required"]

    @pytest.mark.asyncio
    async def test_tool_execute_with_arguments(self) -> None:
        @tool
        async def calculate(a: int, b: int) -> int:
            """Calculate sum."""
            return a + b

        result = await calculate.execute(a=5, b=3)
        assert result == 8

    def test_tool_decorator_multiline_docstring(self) -> None:
        @tool
        async def multi_line_doc(x: str) -> str:
            """First line only.

            Second line should be dropped.
            Third line too.
            """
            return x

        assert "First line only." == multi_line_doc.description

    def test_tool_decorator_no_docstring(self) -> None:
        @tool
        async def no_doc(x: str) -> str:
            return x

        assert no_doc.description == ""

    def test_function_tool_repr(self) -> None:
        @tool
        async def my_tool(x: str) -> str:
            """My tool."""
            return x

        assert repr(my_tool) == "FunctionTool(my_tool)"


class TestToolClass:
    def test_tool_subclass_basic(self) -> None:
        class MyTool(ToolBase):
            @property
            def name(self) -> str:
                return "my_tool"

            @property
            def description(self) -> str:
                return "A test tool"

            @property
            def parameters_schema(self) -> dict:
                return {"type": "object", "properties": {}}

            async def execute(self, **kwargs: Any) -> str:
                return "executed"

        tool_instance = MyTool()
        assert "my_tool" == tool_instance.name
        assert "A test tool" == tool_instance.description

    @pytest.mark.asyncio
    async def test_tool_execute_delegates_to_implementation(self) -> None:
        class OrderTool(ToolBase):
            def __init__(self, order_service: MagicMock):
                self.order_service = order_service

            @property
            def name(self) -> str:
                return "lookup_order"

            @property
            def description(self) -> str:
                return "Look up an order"

            @property
            def parameters_schema(self) -> dict:
                return {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                }

            async def execute(self, **kwargs: Any) -> dict:
                order_id = kwargs.get("order_id")
                return await self.order_service.find(order_id)

        mock_service = MagicMock()
        mock_service.find = AsyncMock(return_value={"id": "123", "status": "shipped"})

        tool_instance = OrderTool(mock_service)
        result = await tool_instance.execute(order_id="123")

        assert result["id"] == "123"
        mock_service.find.assert_called_once_with("123")


class TestToolRegistryBasic:
    def test_empty_registry(self) -> None:
        registry = ToolRegistryImpl()
        assert len(registry.list_tools()) == 0

    def test_register_function_tool(self) -> None:
        @tool
        async def get_user(user_id: str) -> dict:
            """Get user by ID."""
            return {"id": user_id}

        registry = ToolRegistryImpl()
        registry.register(get_user)

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "get_user"

    def test_register_class_tool(self) -> None:
        class SearchTool(ToolBase):
            @property
            def name(self) -> str:
                return "search"

            @property
            def description(self) -> str:
                return "Search for items"

            @property
            def parameters_schema(self) -> dict:
                return {"type": "object", "properties": {}}

            async def execute(self, **kwargs: Any) -> list:
                return []

        registry = ToolRegistryImpl()
        registry.register(SearchTool())

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "search"

    def test_register_duplicate_raises(self) -> None:
        @tool(name="duplicate")
        async def tool_a() -> None:
            """ToolBase A."""
            pass

        @tool(name="duplicate")
        async def tool_b() -> None:
            """ToolBase B."""
            pass

        registry = ToolRegistryImpl()
        registry.register(tool_a)

        with pytest.raises(ValueError, match="already registered") as exc_info:
            registry.register(tool_b)
        assert "duplicate" not in str(exc_info.value)

    def test_unregister(self) -> None:
        @tool
        async def temporary_tool() -> None:
            """Temporary tool."""
            pass

        registry = ToolRegistryImpl()
        registry.register(temporary_tool)
        assert len(registry.list_tools()) == 1

        registry.unregister("temporary_tool")
        assert len(registry.list_tools()) == 0

    def test_get_tool(self) -> None:
        @tool
        async def search(query: str) -> list:
            """Search."""
            return []

        registry = ToolRegistryImpl()
        registry.register(search)

        retrieved = registry.get("search")
        assert retrieved is not None
        assert retrieved.name == "search"

    def test_get_tool_not_found(self) -> None:
        registry = ToolRegistryImpl()
        assert registry.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_execute_tool(self) -> None:
        @tool
        async def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        registry = ToolRegistryImpl()
        registry.register(add)

        result = await registry.execute("add", a=2, b=3)
        assert result.is_ok()
        assert result.unwrap() == 5
