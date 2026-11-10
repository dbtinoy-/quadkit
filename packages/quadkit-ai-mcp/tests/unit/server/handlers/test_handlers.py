"""Unit tests for MCP server handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.exceptions import (
    MCPPromptError,
    MCPResourceError,
    MCPToolCallError,
)
from quadkit.ai.mcp.server.handlers.prompts import PromptHandler
from quadkit.ai.mcp.server.handlers.resources import ResourceHandler
from quadkit.ai.mcp.server.handlers.sampling import SamplingHandler, SamplingResponse
from quadkit.ai.mcp.server.handlers.tools import ToolHandler
from quadkit.result import Err, Ok


class TestToolHandler:
    """Tests for ToolHandler."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create a mock tool provider."""
        provider = MagicMock()
        provider.list_tools = AsyncMock(
            return_value=[
                {
                    "name": "test_tool",
                    "description": "A test tool",
                    "inputSchema": {"type": "object"},
                }
            ]
        )
        provider.call_tool = AsyncMock(return_value="tool result")
        return provider

    @pytest.mark.asyncio
    async def test_init_default(self) -> None:
        """Test handler can be initialized without provider."""
        handler = ToolHandler()
        assert handler._provider is None

    @pytest.mark.asyncio
    async def test_list_tools_no_provider(self) -> None:
        """Test list_tools returns empty list without provider."""
        handler = ToolHandler()
        result = await handler.list_tools()
        assert result.is_ok()
        assert result.unwrap() == {"tools": []}

    @pytest.mark.asyncio
    async def test_list_tools_with_provider(
        self, mock_provider: MagicMock
    ) -> None:
        """Test list_tools returns tools from provider."""
        handler = ToolHandler(tool_provider=mock_provider)
        result = await handler.list_tools()
        assert result.is_ok()
        payload = result.unwrap()
        assert "tools" in payload
        assert len(payload["tools"]) == 1
        mock_provider.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tools_provider_error(
        self, mock_provider: MagicMock
    ) -> None:
        """Test list_tools returns Err when provider listing fails."""
        mock_provider.list_tools = AsyncMock(side_effect=RuntimeError("boom"))
        handler = ToolHandler(tool_provider=mock_provider)
        result = await handler.list_tools()
        assert result.is_err()
        assert isinstance(result.unwrap_err(), MCPToolCallError)

    @pytest.mark.asyncio
    async def test_call_tool_no_provider(self) -> None:
        """Test call_tool returns Err without provider."""
        handler = ToolHandler()
        result = await handler.call_tool("test_tool", {})
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, MCPToolCallError)
        assert "No tool provider" in str(error)

    @pytest.mark.asyncio
    async def test_call_tool_with_provider(
        self, mock_provider: MagicMock
    ) -> None:
        """Test call_tool invokes provider."""
        handler = ToolHandler(tool_provider=mock_provider)
        result = await handler.call_tool("test_tool", {"arg": "value"})
        mock_provider.call_tool.assert_called_once_with("test_tool", {"arg": "value"})
        assert result is not None

    @pytest.mark.asyncio
    async def test_call_tool_propagates_error(
        self, mock_provider: MagicMock
    ) -> None:
        """Test call_tool wraps MCPToolCallError in Err."""
        mock_provider.call_tool = AsyncMock(
            side_effect=MCPToolCallError(message="Tool failed", tool_name="test")
        )
        handler = ToolHandler(tool_provider=mock_provider)
        result = await handler.call_tool("test_tool", {})
        assert result.is_err()
        assert isinstance(result.unwrap_err(), MCPToolCallError)


class TestResourceHandler:
    """Tests for ResourceHandler."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create a mock resource provider."""
        provider = MagicMock()
        provider.list_resources = AsyncMock(
            return_value=[
                {
                    "uri": "file:///test.txt",
                    "name": "test.txt",
                    "description": "A test file",
                }
            ]
        )
        provider.read_resource = AsyncMock(
            return_value={"uri": "file:///test.txt", "mimeType": "text/plain", "text": "content"}
        )
        return provider

    @pytest.mark.asyncio
    async def test_init_default(self) -> None:
        """Test handler can be initialized without provider."""
        handler = ResourceHandler()
        assert handler._provider is None

    @pytest.mark.asyncio
    async def test_list_resources_no_provider(self) -> None:
        """Test list_resources returns empty list without provider."""
        handler = ResourceHandler()
        result = await handler.list_resources()
        assert result.is_ok()
        assert result.unwrap() == {"resources": []}

    @pytest.mark.asyncio
    async def test_list_resources_with_provider(
        self, mock_provider: MagicMock
    ) -> None:
        """Test list_resources returns resources from provider."""
        handler = ResourceHandler(resource_provider=mock_provider)
        result = await handler.list_resources()
        assert result.is_ok()
        payload = result.unwrap()
        assert "resources" in payload
        assert len(payload["resources"]) == 1

    @pytest.mark.asyncio
    async def test_list_resources_provider_error(
        self, mock_provider: MagicMock
    ) -> None:
        """Test list_resources returns Err when provider listing fails."""
        mock_provider.list_resources = AsyncMock(side_effect=RuntimeError("boom"))
        handler = ResourceHandler(resource_provider=mock_provider)
        result = await handler.list_resources()
        assert result.is_err()
        assert isinstance(result.unwrap_err(), MCPResourceError)

    @pytest.mark.asyncio
    async def test_read_resource_no_provider(self) -> None:
        """Test read_resource returns Err without provider."""
        handler = ResourceHandler()
        result = await handler.read_resource("file:///test.txt")
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, MCPResourceError)
        assert "No resource provider" in str(error)

    @pytest.mark.asyncio
    async def test_read_resource_with_provider(
        self, mock_provider: MagicMock
    ) -> None:
        """Test read_resource returns content from provider."""
        handler = ResourceHandler(resource_provider=mock_provider)
        result = await handler.read_resource("file:///test.txt")
        assert result.is_ok()
        assert "contents" in result.unwrap()
        mock_provider.read_resource.assert_called_once_with("file:///test.txt")

    @pytest.mark.asyncio
    async def test_list_templates_no_provider(self) -> None:
        """Test list_templates returns empty without provider."""
        handler = ResourceHandler()
        result = await handler.list_templates()
        assert result.is_ok()
        assert result.unwrap() == {"resourceTemplates": []}

    @pytest.mark.asyncio
    async def test_list_templates_with_provider(
        self, mock_provider: MagicMock
    ) -> None:
        """Test list_templates returns templates from provider."""
        mock_provider.list_templates = AsyncMock(
            return_value=[{"uriTemplate": "file:///{name}"}]
        )
        handler = ResourceHandler(resource_provider=mock_provider)
        result = await handler.list_templates()
        assert result.is_ok()
        payload = result.unwrap()
        assert "resourceTemplates" in payload
        assert len(payload["resourceTemplates"]) == 1


class TestPromptHandler:
    """Tests for PromptHandler."""

    @pytest.fixture
    def mock_provider(self) -> MagicMock:
        """Create a mock prompt provider."""
        provider = MagicMock()
        provider.list_prompts = AsyncMock(
            return_value=[
                {
                    "name": "test_prompt",
                    "description": "A test prompt",
                    "arguments": [],
                }
            ]
        )
        provider.get_prompt = AsyncMock(
            return_value={
                "messages": [{"role": "user", "content": {"type": "text", "text": "Hello"}}]
            }
        )
        return provider

    @pytest.mark.asyncio
    async def test_init_default(self) -> None:
        """Test handler can be initialized without provider."""
        handler = PromptHandler()
        assert handler._provider is None

    @pytest.mark.asyncio
    async def test_list_prompts_no_provider(self) -> None:
        """Test list_prompts returns empty list without provider."""
        handler = PromptHandler()
        result = await handler.list_prompts()
        assert result.is_ok()
        assert result.unwrap() == {"prompts": []}

    @pytest.mark.asyncio
    async def test_list_prompts_with_provider(
        self, mock_provider: MagicMock
    ) -> None:
        """Test list_prompts returns prompts from provider."""
        handler = PromptHandler(prompt_provider=mock_provider)
        result = await handler.list_prompts()
        assert result.is_ok()
        payload = result.unwrap()
        assert "prompts" in payload
        assert len(payload["prompts"]) == 1

    @pytest.mark.asyncio
    async def test_list_prompts_provider_error(
        self, mock_provider: MagicMock
    ) -> None:
        """Test list_prompts returns Err when provider listing fails."""
        mock_provider.list_prompts = AsyncMock(side_effect=RuntimeError("boom"))
        handler = PromptHandler(prompt_provider=mock_provider)
        result = await handler.list_prompts()
        assert result.is_err()
        assert isinstance(result.unwrap_err(), MCPPromptError)

    @pytest.mark.asyncio
    async def test_get_prompt_no_provider(self) -> None:
        """Test get_prompt returns Err without provider."""
        handler = PromptHandler()
        result = await handler.get_prompt("test_prompt")
        assert result.is_err()
        error = result.unwrap_err()
        assert isinstance(error, MCPPromptError)
        assert "No prompt provider" in str(error)

    @pytest.mark.asyncio
    async def test_get_prompt_with_provider(
        self, mock_provider: MagicMock
    ) -> None:
        """Test get_prompt returns prompt from provider."""
        handler = PromptHandler(prompt_provider=mock_provider)
        result = await handler.get_prompt("test_prompt", {"name": "world"})
        assert result.is_ok()
        assert "messages" in result.unwrap()
        mock_provider.get_prompt.assert_called_once_with("test_prompt", {"name": "world"})

    @pytest.mark.asyncio
    async def test_get_prompt_propagates_error(
        self, mock_provider: MagicMock
    ) -> None:
        """Test get_prompt returns Err for MCPPromptError."""
        mock_provider.get_prompt = AsyncMock(
            side_effect=MCPPromptError(message="Prompt failed", prompt_name="test")
        )
        handler = PromptHandler(prompt_provider=mock_provider)
        result = await handler.get_prompt("test_prompt")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), MCPPromptError)


class TestSamplingHandler:
    """Tests for SamplingHandler."""

    @pytest.mark.asyncio
    async def test_create_message_returns_ok_result(self) -> None:
        """Test create_message returns Ok payload when internal handling succeeds."""
        handler = SamplingHandler(llm=MagicMock())
        handler._handle = AsyncMock(  # type: ignore[method-assign]
            return_value=Ok(
                SamplingResponse(
                    role="assistant",
                    content={"type": "text", "text": "hello"},
                    model="test-model",
                    stop_reason="end_turn",
                )
            )
        )

        result = await handler.create_message(messages=[{"role": "user", "content": "hi"}])

        assert result.is_ok()
        payload = result.unwrap()
        assert payload["role"] == "assistant"
        assert payload["model"] == "test-model"

    @pytest.mark.asyncio
    async def test_create_message_returns_err_result(self) -> None:
        """Test create_message returns Err when internal handling fails."""
        handler = SamplingHandler(llm=MagicMock())
        handler._handle = AsyncMock(  # type: ignore[method-assign]
            return_value=Err(MCPToolCallError(message="sampling failed"))
        )

        result = await handler.create_message(messages=[{"role": "user", "content": "hi"}])

        assert result.is_err()
        assert isinstance(result.unwrap_err(), MCPToolCallError)
