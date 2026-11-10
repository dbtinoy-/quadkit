"""Tests for MCP server handlers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestToolHandler:
    """Tests for ToolHandler."""

    def test_constructor(self) -> None:
        from quadkit.ai.mcp.server.handlers.tools import ToolHandler

        handler = ToolHandler()
        assert handler._provider is None

    def test_constructor_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.tools import ToolHandler

        provider = MagicMock()
        handler = ToolHandler(tool_provider=provider)
        assert handler._provider is provider

    @pytest.mark.asyncio
    async def test_list_tools_no_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.tools import ToolHandler

        handler = ToolHandler()
        result = await handler.list_tools()

        assert result.is_ok()
        assert result.unwrap()["tools"] == []

    @pytest.mark.asyncio
    async def test_list_tools_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.tools import ToolHandler

        provider = MagicMock()
        provider.list_tools = AsyncMock(return_value=[{"name": "test", "description": "Test tool"}])
        handler = ToolHandler(tool_provider=provider)
        result = await handler.list_tools()

        assert result.is_ok()
        assert len(result.unwrap()["tools"]) == 1

    @pytest.mark.asyncio
    async def test_call_tool_no_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.tools import ToolHandler

        handler = ToolHandler()
        result = await handler.call_tool("test_tool")

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_call_tool_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.tools import ToolHandler

        provider = MagicMock()
        provider.call_tool = AsyncMock(return_value={"content": [{"type": "text", "text": "ok"}]})
        handler = ToolHandler(tool_provider=provider)
        result = await handler.call_tool("test_tool")

        assert result.is_ok()


class TestResourceHandler:
    """Tests for ResourceHandler."""

    def test_constructor(self) -> None:
        from quadkit.ai.mcp.server.handlers.resources import ResourceHandler

        handler = ResourceHandler()
        assert handler._provider is None

    @pytest.mark.asyncio
    async def test_list_resources_no_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.resources import ResourceHandler

        handler = ResourceHandler()
        result = await handler.list_resources()

        assert result.is_ok()
        assert result.unwrap()["resources"] == []

    @pytest.mark.asyncio
    async def test_list_templates_no_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.resources import ResourceHandler

        handler = ResourceHandler()
        result = await handler.list_templates()

        assert result.is_ok()


class TestPromptHandler:
    """Tests for PromptHandler."""

    def test_constructor(self) -> None:
        from quadkit.ai.mcp.server.handlers.prompts import PromptHandler

        handler = PromptHandler()
        assert handler._provider is None

    @pytest.mark.asyncio
    async def test_list_prompts_no_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.prompts import PromptHandler

        handler = PromptHandler()
        result = await handler.list_prompts()

        assert result.is_ok()
        assert result.unwrap()["prompts"] == []

    @pytest.mark.asyncio
    async def test_get_prompt_no_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.prompts import PromptHandler

        handler = PromptHandler()
        result = await handler.get_prompt(name="test")

        assert result.is_err()


class TestSamplingHandler:
    """Tests for SamplingHandler."""

    def test_requires_llm_client(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingHandler

        llm = MagicMock()
        handler = SamplingHandler(llm=llm)
        assert handler._llm is llm


class TestLoggingHandler:
    """Tests for LoggingHandler."""

    def test_constructor(self) -> None:
        from quadkit.ai.mcp.server.handlers.logging_handler import LoggingHandler

        handler = LoggingHandler()
        assert handler._min_level == "info"

    def test_constructor_with_level(self) -> None:
        from quadkit.ai.mcp.server.handlers.logging_handler import LoggingHandler

        handler = LoggingHandler(min_level="debug")
        assert handler._min_level == "debug"

    def test_invalid_level_raises(self) -> None:
        from quadkit.ai.mcp.server.handlers.logging_handler import LoggingHandler

        with pytest.raises(ValueError, match="Invalid MCP log level"):
            LoggingHandler(min_level="invalid")


class TestHandlerExports:
    """Tests for handlers module exports."""

    def test_all_exported(self) -> None:
        from quadkit.ai.mcp.server import handlers

        expected = [
            "LoggingHandler",
            "PromptHandler",
            "ResourceHandler",
            "SamplingHandler",
            "SamplingRequest",
            "SamplingResponse",
            "ToolHandler",
        ]
        for name in expected:
            assert hasattr(handlers, name)