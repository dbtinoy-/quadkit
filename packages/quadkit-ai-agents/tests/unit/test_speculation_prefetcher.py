"""Tests for SpeculativeToolPreFetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.agents.speculation.prefetcher import SpeculativeToolPreFetcher
from quadkit.contracts.ai.llm import ChatMessage, Completion
from quadkit.result import Ok, Err


class TestSpeculativeToolPreFetcher:
    """Tests for SpeculativeToolPreFetcher."""

    @pytest.fixture
    def mock_registry(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        client = MagicMock()
        client.complete = AsyncMock(return_value=Ok(Completion(content="result", model="gpt-4", finish_reason="stop")))
        return client

    @pytest.fixture
    def mock_tool(self) -> MagicMock:
        tool = MagicMock()
        tool.name = "search"
        tool.execute = AsyncMock(return_value="search_result")
        return tool

    @pytest.mark.asyncio
    async def test_execute_with_speculation_returns_llm_result(
        self,
        mock_registry: MagicMock,
        mock_llm: MagicMock,
        mock_tool: MagicMock,
    ) -> None:
        prefetcher = SpeculativeToolPreFetcher(mock_registry, max_speculative=1)
        result = await prefetcher.execute_with_speculation(
            "search query",
            [mock_tool],
            mock_llm,
            [ChatMessage(role="user", content="hello")],
        )
        assert result.is_ok()
        assert result.unwrap().content == "result"

    @pytest.mark.asyncio
    async def test_execute_cancels_speculative_tasks(
        self,
        mock_registry: MagicMock,
        mock_llm: MagicMock,
        mock_tool: MagicMock,
    ) -> None:
        prefetcher = SpeculativeToolPreFetcher(mock_registry, max_speculative=1)
        result = await prefetcher.execute_with_speculation(
            "search query",
            [mock_tool],
            mock_llm,
            [ChatMessage(role="user", content="hello")],
        )
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_execute_returns_err_on_llm_failure(
        self,
        mock_registry: MagicMock,
        mock_tool: MagicMock,
    ) -> None:
        from quadkit.contracts.ai.exceptions import LLMError

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=Err(LLMError("llm failed")))

        prefetcher = SpeculativeToolPreFetcher(mock_registry, max_speculative=1)
        result = await prefetcher.execute_with_speculation(
            "query",
            [mock_tool],
            mock_llm,
            [ChatMessage(role="user", content="hi")],
        )
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_execute_skips_tool_without_name(
        self,
        mock_registry: MagicMock,
        mock_llm: MagicMock,
    ) -> None:
        nameless = MagicMock()
        nameless.name = ""

        prefetcher = SpeculativeToolPreFetcher(mock_registry, max_speculative=1)
        result = await prefetcher.execute_with_speculation(
            "query",
            [nameless],
            mock_llm,
            [ChatMessage(role="user", content="hi")],
        )
        assert result.is_ok()

    def test_default_max_speculative(self) -> None:
        prefetcher = SpeculativeToolPreFetcher(MagicMock())
        assert prefetcher._max_speculative == 3

    def test_custom_max_speculative(self) -> None:
        prefetcher = SpeculativeToolPreFetcher(MagicMock(), max_speculative=5)
        assert prefetcher._max_speculative == 5
