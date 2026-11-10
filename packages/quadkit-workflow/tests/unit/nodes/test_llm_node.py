"""Unit tests for LLMNode workflow node."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.workflow.nodes.llm_node import LLMNode
from quadkit.result import Ok


class TestLLMNode:
    def test_node_initialization(self) -> None:
        llm = MagicMock()
        node = LLMNode("llm", llm=llm, prompt_template="Hello {name}")
        assert node.name == "llm"
        assert node._llm is llm
        assert node._prompt_template == "Hello {name}"

    @pytest.mark.asyncio
    async def test_node_renders_prompt(self) -> None:
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=Ok(_MockCompletion("response")))
        node = LLMNode("llm", llm=llm, prompt_template="Hello {name}")
        result = await node.execute({"name": "Alice"})
        llm.complete.assert_called_once()
        call_args = llm.complete.call_args[0][0]
        user_msg = call_args[0] if call_args[0].role == "user" else call_args[1]
        assert "Alice" in user_msg.content

    @pytest.mark.asyncio
    async def test_node_calls_llm(self) -> None:
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=Ok(_MockCompletion("test response")))
        node = LLMNode("llm", llm=llm, prompt_template="{input}")
        result = await node.execute({"input": "test input"})
        llm.complete.assert_called_once()
        assert result == {"output": "test response"}

    @pytest.mark.asyncio
    async def test_node_handles_llm_error(self) -> None:
        llm = MagicMock()
        llm.complete = AsyncMock(side_effect=RuntimeError("API failed"))
        node = LLMNode("llm", llm=llm, prompt_template="{input}")
        result = await node.execute({"input": "test"})
        assert result == {"output": "LLM request failed."}
        assert "API failed" not in result["output"]

    @pytest.mark.asyncio
    async def test_node_extracts_response(self) -> None:
        llm = MagicMock()
        llm.complete = AsyncMock(return_value=Ok(_MockCompletion("extracted text")))
        node = LLMNode("llm", llm=llm, prompt_template="{input}", output_key="result")
        result = await node.execute({"input": "test"})
        assert result == {"result": "extracted text"}


class _MockCompletion:
    def __init__(self, content: str) -> None:
        self.content = content
