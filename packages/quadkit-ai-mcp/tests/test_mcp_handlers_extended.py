"""Additional tests for MCP server handler modules."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestSamplingRequest:
    """Tests for SamplingRequest dataclass."""

    def test_creation(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingRequest

        req = SamplingRequest(messages=[{"role": "user", "content": {"type": "text", "text": "hello"}}])
        assert len(req.messages) == 1

    def test_with_model_preferences(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingRequest

        req = SamplingRequest(messages=[], model_preferences={"hints": ["gpt-4"]})
        assert req.model_preferences == {"hints": ["gpt-4"]}

    def test_with_system_prompt(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingRequest

        req = SamplingRequest(messages=[], system_prompt="You are a helpful assistant.")
        assert req.system_prompt == "You are a helpful assistant."


class TestSamplingResponse:
    """Tests for SamplingResponse dataclass."""

    def test_creation(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingResponse

        resp = SamplingResponse(
            role="assistant",
            content={"type": "text", "text": "Hello!"},
            model="gpt-4",
        )
        assert resp.role == "assistant"
        assert resp.content["text"] == "Hello!"

    def test_to_dict(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingResponse

        resp = SamplingResponse(role="assistant", content={"type": "text", "text": "Hi"}, model="gpt-4")
        result = resp.to_dict()
        assert result["role"] == "assistant"
        assert result["model"] == "gpt-4"

    def test_to_dict_with_stop_reason(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingResponse

        resp = SamplingResponse(role="assistant", content={"type": "text", "text": "Hi"}, model="gpt-4", stop_reason="end_turn")
        result = resp.to_dict()
        assert result["stopReason"] == "end_turn"


class TestResourceHandlerListResources:
    """Tests for ResourceHandler list methods."""

    @pytest.mark.asyncio
    async def test_list_resources_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.resources import ResourceHandler

        provider = MagicMock()
        provider.list_resources = AsyncMock(return_value=[{"uri": "file://test", "name": "Test"}])
        handler = ResourceHandler(resource_provider=provider)
        result = await handler.list_resources()

        assert result.is_ok()
        assert len(result.unwrap()["resources"]) == 1

    @pytest.mark.asyncio
    async def test_read_resource_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.resources import ResourceHandler

        provider = MagicMock()
        provider.read_resource = AsyncMock(return_value={"uri": "file://test", "text": "content"})
        handler = ResourceHandler(resource_provider=provider)
        result = await handler.read_resource(uri="file://test")

        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_list_templates_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.resources import ResourceHandler

        provider = MagicMock()
        provider.list_templates = AsyncMock(return_value=[])
        handler = ResourceHandler(resource_provider=provider)
        result = await handler.list_templates()

        assert result.is_ok()


class TestPromptHandlerWithProvider:
    """Tests for PromptHandler with provider."""

    @pytest.mark.asyncio
    async def test_list_prompts_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.prompts import PromptHandler

        provider = MagicMock()
        provider.list_prompts = AsyncMock(return_value=[{"name": "test", "description": "Test prompt"}])
        handler = PromptHandler(prompt_provider=provider)
        result = await handler.list_prompts()

        assert result.is_ok()
        assert len(result.unwrap()["prompts"]) == 1

    @pytest.mark.asyncio
    async def test_get_prompt_with_provider(self) -> None:
        from quadkit.ai.mcp.server.handlers.prompts import PromptHandler

        provider = MagicMock()
        provider.get_prompt = AsyncMock(return_value={"messages": []})
        handler = PromptHandler(prompt_provider=provider)
        result = await handler.get_prompt(name="summarize")

        assert result.is_ok()


class TestSamplingHandlerWithLLM:
    """Tests for SamplingHandler with LLM client."""

    @pytest.mark.asyncio
    async def test_handle_with_llm(self) -> None:
        from quadkit.ai.mcp.server.handlers.sampling import SamplingHandler, SamplingRequest

        llm = MagicMock()
        handler = SamplingHandler(llm=llm)
        assert handler._llm is llm